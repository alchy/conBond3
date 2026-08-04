"""Extrakční vrstva: pole, šablony, atomy, koše. Mockup — koše a registr.

Modul se staví postupně (README-EXTRAKCNI_VRSTVA.md); dnes umí projít
rozparsovanou větu posuvným oknem (koše), rozvinout metadata na vážené
hodnoty, spočítat aktivace per atribut=hodnota a držet pro ně append-only
registr vertikál — základ maticové podoby pole. K tomu kukátko (viewer).
"""

from cb_field.corpus import Corpus
from cb_field.corpusfile import (
    CorpusBlock,
    CorpusFile,
    CorpusQuestion,
    add_to_corpus,
    build_corpus,
    etalon_entries,
    load_corpus_file,
)
from cb_field.field import FieldBasket, SentenceField
from cb_field.registry import VerticalRegistry
from cb_field.service import (
    CLOSED_UPOS,
    DEFAULT_WEIGHT,
    FEAT_SLOTS,
    WEIGHT_MAX,
    WEIGHT_MIN,
    Activations,
    Basket,
    MetaValue,
    Representation,
    activations,
    build_baskets,
    expand_basket,
    expand_token,
    is_question,
    seed_anchor_links,
)
from cb_field.viewer import Visualizer, visualize

#: Verze modulu; roste s každou změnou chování. Objektové ukládání košů
#: zahozeno v 0.1.0 ve prospěch maticové cesty; 0.2.0 otázková strana;
#: 0.5.0 třída SentenceField jako pracovní úroveň (věta → pole → matice);
#: 0.6.0 Corpus a fixovaný korpus v JSON (krok 1 stavby cb_bond);
#: 0.7.0 custom sloty registru + CUSTOM= aktivace pole (krok 3 § 3).
__version__ = "0.7.0"

__all__ = [
    "Corpus",
    "CorpusBlock",
    "CorpusFile",
    "CorpusQuestion",
    "load_corpus_file",
    "add_to_corpus",
    "build_corpus",
    "etalon_entries",
    "SentenceField",
    "FieldBasket",
    "Basket",
    "MetaValue",
    "build_baskets",
    "expand_basket",
    "expand_token",
    "activations",
    "Activations",
    "Representation",
    "VerticalRegistry",
    "CLOSED_UPOS",
    "FEAT_SLOTS",
    "DEFAULT_WEIGHT",
    "WEIGHT_MIN",
    "WEIGHT_MAX",
    "is_question",
    "seed_anchor_links",
    "Visualizer",
    "visualize",
    "__version__",
]
