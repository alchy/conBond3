"""Testy modulu cb-udpipe.

Spouštějí se přes projektový interpret, nikdy přímo systémovým Pythonem:

    ./run-python -m unittest discover -s cb_udpipe -t .

Testy, které potřebují běžící službu, si ji spustí samy na portu 0 a po sobě
uklidí. Testy `conllu`, `tokenize` a `cache` běžící službu nepotřebují vůbec —
je to čistá logika nad daty a to je záměr, ne náhoda.
"""
