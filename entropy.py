import math
from collections import Counter, deque

class ChaoticSwitchDetector:
    """
    Аналізатор стабільності фокусу користувача на основі оцінки інформаційної ентропії.
    """
    def __init__(self, window_size_seconds: int = 60, sampling_interval: float = 1.0):
        # Визначаємо розмір черги для збереження історії перемикань за останні N секунд
        self.max_len = int(window_size_seconds / sampling_interval)
        self.history = deque(maxlen=self.max_len)

    def record_state(self, app_name: str):
        """Реєстрація назви активного додатка у ковзній черзі."""
        if app_name:
            self.history.append(app_name)

    def calculate_entropy(self) -> float:
        """
        Обчислення ентропії Шеннона для поточного розподілу уваги.
        """
        if not self.history:
            return 0.0
        
        total_samples = len(self.history)
        counts = Counter(self.history)
        entropy = 0.0
        
        for count in counts.values():
            p_i = count / total_samples
            entropy -= p_i * math.log2(p_i)
            
        return entropy
      
