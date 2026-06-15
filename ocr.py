import asyncio
import io
import sys
import logging
from concurrent.futures import ThreadPoolExecutor
from PIL import Image

PLATFORM = sys.platform
HAS_NATIVE_OCR = False
logger = logging.getLogger("DopamineFastingShell")

# Нативна ініціалізація OCR для Windows
if PLATFORM == "win32":
    try:
        from winrt.windows.media.ocr import OcrEngine
        from winrt.windows.globalization import Language
        from winrt.windows.graphics.imaging import SoftwareBitmap, BitmapPixelFormat, BitmapAlphaMode
        from winrt.windows.storage.streams import DataWriter
        HAS_NATIVE_OCR = True
    except ImportError:
        logger.warning("Модулі Windows WinRT OCR не знайдені.")

# Нативна ініціалізація OCR для macOS
elif PLATFORM == "darwin":
    try:
        import Quartz
        import Vision
        from Cocoa import NSData
        HAS_NATIVE_OCR = True
    except ImportError:
        logger.warning("Модулі macOS Vision OCR не знайдені.")


class NativeOCRScanner:
    """
    Локальний кросплатформний OCR-сканер без використання зовнішніх API.
    """
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=1)

    async def scan_image(self, pil_img: Image.Image) -> str:
        """
        Асинхронний метод сканування зображення, що делегує виконання у фоновий потік.
        """
        if not HAS_NATIVE_OCR:
            logger.warning("Локальний нативний OCR рушій не доступний у цій системі.")
            return ""

        loop = asyncio.get_running_loop()
        if PLATFORM == "win32":
            return await loop.run_in_executor(self.executor, self._windows_ocr_sync, pil_img)
        elif PLATFORM == "darwin":
            return await loop.run_in_executor(self.executor, self._macos_ocr_sync, pil_img)
        return ""

    def _windows_ocr_sync(self, pil_img: Image.Image) -> str:
        """Синхронний Win32 метод розпізнавання через Windows.Media.Ocr."""
        try:
            rgba_img = pil_img.convert("RGBA")
            width, height = rgba_img.size
            img_bytes = rgba_img.tobytes()

            writer = DataWriter()
            writer.write_bytes(list(img_bytes))
            buffer = writer.detach_buffer()

            software_bitmap = SoftwareBitmap(
                BitmapPixelFormat.RGBA8, 
                width, 
                height, 
                BitmapAlphaMode.STRAIGHT
            )
            software_bitmap.copy_from_buffer(buffer)

            lang = Language("en-US")
            if not OcrEngine.is_language_supported(lang):
                return ""
                
            engine = OcrEngine.try_create_from_language(lang)
            if not engine:
                return ""

            async def run_recognition():
                ocr_result = await engine.recognize_async(software_bitmap)
                return ocr_result.text

            internal_loop = asyncio.new_event_loop()
            return internal_loop.run_until_complete(run_recognition())
        except Exception as e:
            logger.error(f"Помилка Windows WinRT OCR: {e}")
            return ""

    def _macos_ocr_sync(self, pil_img: Image.Image) -> str:
        """Синхронний macOS метод розпізнавання через Apple Vision Framework (VNRecognizeTextRequest)."""
        try:
            img_byte_arr = io.BytesIO()
            pil_img.save(img_byte_arr, format='PNG')
            img_bytes = img_byte_arr.getvalue()

            ns_data = NSData.dataWithBytes_length_(img_bytes, len(img_bytes))
            ci_image = Quartz.CIImage.imageWithData_(ns_data)

            request_handler = Vision.VNImageRequestHandler.alloc().initWithCIImage_options_(ci_image, None)
            ocr_results =

            def completion_handler(request, error):
                if error:
                    return
                observations = request.results()
                if observations:
                    for obs in observations:
                        top_candidate = obs.topCandidates_(1)
                        if top_candidate:
                            ocr_results.append(top_candidate.string())

            request = Vision.VNRecognizeTextRequest.alloc().initWithCompletionHandler_(completion_handler)
            request.setRecognitionLevel_(0)  # Рівень Accurate (0)
            request.setUsesLanguageCorrection_(True)

            success, error = request_handler.performRequests_error_([request], None)
            if not success:
                return ""

            return " ".join(ocr_results)
        except Exception as e:
            logger.error(f"Помилка macOS Vision OCR: {e}")
            return ""
          
