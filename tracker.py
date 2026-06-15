import asyncio
import time
import logging
from concurrent.futures import ThreadPoolExecutor
from PIL import Image

import config
from entropy import ChaoticSwitchDetector
from ocr import NativeOCRScanner

try:
    import pywinctl as pwc
except ImportError:
    pwc = None

try:
    import psutil
except ImportError:
    psutil = None

try:
    from mss import mss
except ImportError:
    mss = None

logger = logging.getLogger("DopamineFastingShell")

class FocusTracker:
    """
    Координатор фокусу та когнітивних інтервенцій.
    """
    def __init__(self):
        self.check_interval = config.CHECK_INTERVAL
        self.chaos_threshold = config.CHAOS_THRESHOLD
        self.detector = ChaoticSwitchDetector(window_size_seconds=60, sampling_interval=self.check_interval)
        self.ocr_scanner = NativeOCRScanner()
        # Потоки для операцій I/O та викликів низькорівневих системних API
        self.thread_executor = ThreadPoolExecutor(max_workers=2)

    async def get_active_window_info(self) -> dict:
        """
        Асинхронний запит інформації про активне вікно без блокування event loop.
        """
        if not pwc:
            return {}
        
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self.thread_executor, self._get_active_window_sync)

    def _get_active_window_sync(self) -> dict:
        """Синхронний низькорівневий запит характеристик вікна."""
        try:
            win = pwc.getActiveWindow()
            if win:
                pid = win.getPID()
                app_name = "Unknown"
                if psutil and pid > 0:
                    try:
                        app_name = psutil.Process(pid).name()
                    except psutil.NoSuchProcess:
                        app_name = win.getAppName()
                else:
                    app_name = win.getAppName()

                return {
                    "title": win.title,
                    "app_name": app_name,
                    "coords": {
                        "top": win.top,
                        "left": win.left,
                        "width": win.width,
                        "height": win.height
                    }
                }
        except Exception as e:
            logger.debug(f"Помилка визначення активного вікна: {e}")
        return {}

    async def capture_window_area(self, coords: dict) -> Image.Image:
        """
        Асинхронне отримання знімка екрана у межах габаритів активного вікна.
        """
        if not mss:
            return None
        
        def sync_capture():
            with mss() as sct:
                monitor = {
                    "top": max(0, int(coords["top"])),
                    "left": max(0, int(coords["left"])),
                    "width": max(100, int(coords["width"])),
                    "height": max(100, int(coords["height"]))
                }
                screenshot = sct.grab(monitor)
                # Перетворюємо сирий буфер BGRA в PIL Image RGB
                return Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
            
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self.thread_executor, sync_capture)

    async def handle_intervention(self, app_name: str, trigger_word: str):
        """
        Метод запуску когнітивної інтервенції при виявленні ознак когнітивного тупика.
        """
        logger.warning(
            f"\n"
            f"======================================================================\n"
            f"⚠️ ВИЯВЛЕНО КОГНІТИВНИЙ ТУПИК!\n"
            f"Ваш рівень хаотичності перемикань перевищив норму.\n"
            f"Активний додаток: {app_name}\n"
            f"Виявлено тригерний деструктивний елемент: '{trigger_word}'\n"
            f"Порада: Зробіть глибокий подих і поверніться до основного завдання.\n"
            f"======================================================================"
        )

    async def start_monitoring(self):
        """
        Головний асинхронний життєвий цикл трекера фокусу.
        """
        logger.info("Моніторинг робочого стану активовано.")
        while True:
            start_time = time.time()
            win_info = await self.get_active_window_info()
            
            if win_info:
                app_name = win_info.get("app_name", "")
                title = win_info.get("title", "")
                self.detector.record_state(app_name)
                
                # Розрахунок поточної ентропії поведінки
                current_entropy = self.detector.calculate_entropy()
                logger.info(f"Активний додаток: {app_name} | Ентропія: {current_entropy:.4f}")

                # Якщо ентропія вища за ліміт — робимо знімок вікна та аналізуємо текст
                if current_entropy > self.chaos_threshold:
                    coords = win_info.get("coords")
                    if coords:
                        pil_img = await self.capture_window_area(coords)
                        if pil_img:
                            ocr_text = await self.ocr_scanner.scan_image(pil_img)
                            ocr_text_lower = ocr_text.lower()
                            
                            # Пошук слів-тригерів у розпізнаному OCR тексті та у заголовку вікна
                            combined_text = f"{ocr_text_lower} {title.lower()}"
                            for trigger in config.PROCRASTINATION_TRIGGERS:
                                if trigger in combined_text:
                                    await self.handle_intervention(app_name, trigger)
                                    break

            # Компенсація часу виконання аналізу для утримання стабільного кроку циклу
            elapsed = time.time() - start_time
            sleep_time = max(0.1, self.check_interval - elapsed)
            await asyncio.sleep(sleep_time)
                  
