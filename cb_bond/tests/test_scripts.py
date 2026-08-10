"""Měřicí skripty musí jít aspoň naimportovat.

SyntaxError v měřicím skriptu se jinak pozná až při spuštění protokolu
(ARCHITECTURE_REVIEW příloha A) — tenhle test ho sráží do běžné testovací
smyčky. Nespouští `main()`: modul se jen načte, takže nepotřebuje korpusy
ani běžící UDPipe. Importují se jen skripty s `__main__` guardem —
`prejimka-zrcadlo.py` ho nemá a import by ho spustil.
"""
import importlib.util
import unittest
from pathlib import Path

SKRIPTY = Path(__file__).parent.parent / "scripts"
MERICI = ("protokol.py", "rozklad-skore.py")


class TestMericiSkriptyJdouNacist(unittest.TestCase):
    def test_merici_skripty_jdou_naimportovat(self):
        for jmeno in MERICI:
            with self.subTest(skript=jmeno):
                cesta = SKRIPTY / jmeno
                spec = importlib.util.spec_from_file_location(
                    cesta.stem.replace("-", "_"), cesta)
                modul = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(modul)


if __name__ == "__main__":
    unittest.main()
