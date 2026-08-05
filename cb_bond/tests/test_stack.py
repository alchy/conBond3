"""Testy `ServiceStack` — cb-bond jako řídicí vrstva nad službami.

Co se tady hlídá, je pořadí a hranice. Pořadí proto, že udpipe loguje do
loggeru už při vlastním startu, takže obrácené pořadí by první záznamy
zahodilo. Hranice proto, že cizí službu smí spouštět jen její vlastní
ovládací program — kdyby cb-bond logiku startu duplikoval, existovala by
dvakrát a rozešla by se.

Test nesmí potřebovat běžící službu (§ 13), takže se sem dosazuje atrapa
dotazu na zdraví a atrapa spouštění.
"""

import unittest

from cb_bond.stack import Dependency, ServiceStack


class _Runner:
    """Atrapa spouštění: pamatuje si, co a v jakém pořadí by spustila."""

    def __init__(self, nabehne=True):
        self.volani = []
        self.nabehne = nabehne

    def __call__(self, dependency, prikaz):
        self.volani.append((dependency.name, prikaz))
        return self.nabehne


def _zdravi(bezici: set):
    """Atrapa dotazu na zdraví: běží jen jmenované služby."""
    def dotaz(dependency):
        return {"status": "ok"} if dependency.name in bezici else None
    return dotaz


ZAVISLOSTI = (
    Dependency("cb-logger", "./cb-logger.py", "http://127.0.0.1:42100"),
    Dependency("cb-udpipe", "./cb-udpipe.py", "http://127.0.0.1:42200"),
)


class TestKontrola(unittest.TestCase):

    def test_check_rekne_o_KAZDE_zavislosti_jestli_bezi(self):
        stack = ServiceStack(ZAVISLOSTI, health=_zdravi({"cb-logger"}),
                             runner=_Runner(), verbose=False)

        stav = stack.check()

        self.assertEqual([s["name"] for s in stav],
                         ["cb-logger", "cb-udpipe"])
        self.assertTrue(stav[0]["running"])
        self.assertFalse(stav[1]["running"])

    def test_check_zachova_poradi_ZAVISLOSTI(self):
        # logger první: udpipe do něj loguje už při vlastním startu
        stack = ServiceStack(ZAVISLOSTI, health=_zdravi(set()),
                             runner=_Runner(), verbose=False)

        self.assertEqual([s["name"] for s in stack.check()],
                         ["cb-logger", "cb-udpipe"])


class TestSpousteni(unittest.TestCase):

    def test_ensure_spusti_jen_to_co_NEBEZI(self):
        runner = _Runner()
        stack = ServiceStack(ZAVISLOSTI, health=_zdravi({"cb-logger"}),
                             runner=runner, verbose=False)

        spustene = stack.ensure()

        self.assertEqual(spustene, ["cb-udpipe"])
        self.assertEqual(runner.volani, [("cb-udpipe", "start")])

    def test_ensure_spousti_v_poradi_LOGGER_PRVNI(self):
        runner = _Runner()
        stack = ServiceStack(ZAVISLOSTI, health=_zdravi(set()),
                             runner=runner, verbose=False)

        stack.ensure()

        self.assertEqual([jmeno for jmeno, _ in runner.volani],
                         ["cb-logger", "cb-udpipe"])

    def test_ensure_bez_spousteni_jen_ohlasi_co_chybi(self):
        # `--no-deps`: člověk si služby řídí sám a nechce překvapení
        runner = _Runner()
        stack = ServiceStack(ZAVISLOSTI, health=_zdravi(set()),
                             runner=runner, verbose=False)

        chybi = stack.ensure(start=False)

        self.assertEqual(chybi, ["cb-logger", "cb-udpipe"])
        self.assertEqual(runner.volani, [])

    def test_sluzba_ktera_nenabehla_je_HLASITA_chyba(self):
        # tichý běh dál by znamenal cb-bond, který se tváří zdravě
        # a padne až u prvního rozboru — daleko od příčiny (§ 9)
        stack = ServiceStack(ZAVISLOSTI, health=_zdravi(set()),
                             runner=_Runner(nabehne=False), verbose=False)

        with self.assertRaises(RuntimeError) as chyba:
            stack.ensure()
        self.assertIn("cb-logger", str(chyba.exception))


class TestZastaveni(unittest.TestCase):

    def test_stop_jde_v_OPACNEM_poradi(self):
        # zastavit logger první by zahodilo záznamy o zastavení udpipe
        runner = _Runner()
        stack = ServiceStack(ZAVISLOSTI, health=_zdravi({"cb-logger",
                                                         "cb-udpipe"}),
                             runner=runner, verbose=False)

        stack.stop()

        self.assertEqual([jmeno for jmeno, _ in runner.volani],
                         ["cb-udpipe", "cb-logger"])


class TestPrehled(unittest.TestCase):

    def test_report_uvadi_jmeno_stav_i_adresu(self):
        stack = ServiceStack(ZAVISLOSTI, health=_zdravi({"cb-logger"}),
                             runner=_Runner(), verbose=False)

        prehled = stack.report()

        self.assertIn("cb-logger", prehled)
        self.assertIn("BĚŽÍ", prehled)
        self.assertIn("NEBĚŽÍ", prehled)
        self.assertIn("42200", prehled)


if __name__ == "__main__":
    unittest.main()
