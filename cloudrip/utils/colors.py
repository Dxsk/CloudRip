"""Terminal color utilities."""

from colorama import Fore, Style, init

init(autoreset=True)


class Colors:
    """Terminal color constants."""

    RED = Fore.RED
    GREEN = Fore.GREEN
    BLUE = Fore.LIGHTBLUE_EX
    YELLOW = Fore.LIGHTYELLOW_EX
    WHITE = Fore.WHITE
    CYAN = Fore.CYAN
    RESET = Style.RESET_ALL
