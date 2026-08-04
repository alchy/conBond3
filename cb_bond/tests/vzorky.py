"""Zmražené věty pro testy cb_bond — skutečné výstupy UDPipe.

Test nesmí potřebovat běžící službu (§ 13 politiky), takže rozbory stojí
v kódu jako literály. Hodnoty jsou z UDPipe 2 (model cs_all-ud-2.17,
tokenizér 6247b8b7a5c8, pořízeno 2026-08-04) — kdo je mění, mění
zemní pravdu všech přejímek, které se o ně opírají.
"""

from cb_udpipe import Token


class Veta:
    """Rozparsovaná věta v podobě, v jaké chodí z cb_udpipe."""

    def __init__(self, source: str, tokens) -> None:
        self.source = source
        self.tokens = tuple(tokens)


#: „V těch dnech přišel Ježíš z Nazareta v Galileji a byl v Jordánu
#: pokřtěn od Jana." — vzorová věta zadání (Mk 1,9). Je na ní vidět celý
#: krok 2: 8 uzlů, 7 hran, a rozdíl Jordán × Galilej, který pytel nevidí.
KRESTA = Veta(
    "V těch dnech přišel Ježíš z Nazareta v Galileji a byl v Jordánu "
    "pokřtěn od Jana.",
    (
        Token(id=1, form="V", lemma="v", upos="ADP",
              xpos="RR--6----------",
              feats={"AdpType": "Prep", "Case": "Loc"},
              head=3, deprel="case", deps=None, misc=None),
        Token(id=2, form="těch", lemma="ten", upos="DET",
              xpos="PDXP6----------",
              feats={"Case": "Loc", "Number": "Plur", "PronType": "Dem"},
              head=3, deprel="det", deps=None, misc=None),
        Token(id=3, form="dnech", lemma="den", upos="NOUN",
              xpos="NNIP6-----A----",
              feats={"Animacy": "Inan", "Case": "Loc", "Gender": "Masc",
                     "Number": "Plur"},
              head=4, deprel="obl", deps=None, misc=None),
        Token(id=4, form="přišel", lemma="přijít", upos="VERB",
              xpos="VpYS----R-AAP--",
              feats={"Aspect": "Perf", "Gender": "Masc", "Number": "Sing",
                     "Polarity": "Pos", "Tense": "Past", "VerbForm": "Part",
                     "Voice": "Act"},
              head=0, deprel="root", deps=None, misc=None),
        Token(id=5, form="Ježíš", lemma="Ježíš", upos="PROPN",
              xpos="NNMS1-----A----",
              feats={"Animacy": "Anim", "Case": "Nom", "Gender": "Masc",
                     "NameType": "Giv", "Number": "Sing"},
              head=4, deprel="nsubj", deps=None, misc=None),
        Token(id=6, form="z", lemma="z", upos="ADP",
              xpos="RR--2----------",
              feats={"AdpType": "Prep", "Case": "Gen"},
              head=7, deprel="case", deps=None, misc=None),
        Token(id=7, form="Nazareta", lemma="Nazareto", upos="PROPN",
              xpos="NNNS2-----A----",
              feats={"Case": "Gen", "Gender": "Neut", "NameType": "Geo",
                     "Number": "Sing"},
              head=4, deprel="obl", deps=None, misc=None),
        Token(id=8, form="v", lemma="v", upos="ADP",
              xpos="RR--6----------",
              feats={"AdpType": "Prep", "Case": "Loc"},
              head=9, deprel="case", deps=None, misc=None),
        Token(id=9, form="Galileji", lemma="Galilej", upos="PROPN",
              xpos="NNFS6-----A----",
              feats={"Case": "Loc", "Gender": "Fem", "NameType": "Geo",
                     "Number": "Sing"},
              head=4, deprel="obl", deps=None, misc=None),
        Token(id=10, form="a", lemma="a", upos="CCONJ",
              xpos="J^-------------", feats=None,
              head=14, deprel="cc", deps=None, misc=None),
        Token(id=11, form="byl", lemma="být", upos="AUX",
              xpos="VpYS----R-AAI--",
              feats={"Aspect": "Imp", "Gender": "Masc", "Number": "Sing",
                     "Polarity": "Pos", "Tense": "Past", "VerbForm": "Part",
                     "Voice": "Act"},
              head=14, deprel="aux:pass", deps=None, misc=None),
        Token(id=12, form="v", lemma="v", upos="ADP",
              xpos="RR--6----------",
              feats={"AdpType": "Prep", "Case": "Loc"},
              head=13, deprel="case", deps=None, misc=None),
        Token(id=13, form="Jordánu", lemma="Jordán", upos="PROPN",
              xpos="NNIS6-----A----",
              feats={"Animacy": "Inan", "Case": "Loc", "Gender": "Masc",
                     "NameType": "Geo", "Number": "Sing"},
              head=14, deprel="obl", deps=None, misc=None),
        Token(id=14, form="pokřtěn", lemma="pokřtěný", upos="ADJ",
              xpos="VsYS----X-APP--",
              feats={"Aspect": "Perf", "Degree": "Pos", "Gender": "Masc",
                     "Number": "Sing", "Polarity": "Pos", "Variant": "Short",
                     "VerbForm": "Part", "Voice": "Pass"},
              head=4, deprel="conj", deps=None, misc=None),
        Token(id=15, form="od", lemma="od", upos="ADP",
              xpos="RR--2----------",
              feats={"AdpType": "Prep", "Case": "Gen"},
              head=16, deprel="case", deps=None, misc=None),
        Token(id=16, form="Jana", lemma="Jan", upos="PROPN",
              xpos="NNMS2-----A----",
              feats={"Animacy": "Anim", "Case": "Gen", "Gender": "Masc",
                     "NameType": "Giv", "Number": "Sing"},
              head=14, deprel="obl:arg", deps=None, misc=None),
        Token(id=17, form=".", lemma=".", upos="PUNCT",
              xpos="Z:-------------", feats=None,
              head=4, deprel="punct", deps=None, misc=None),
    ))

#: „Gravitace je síla působící mezi tělesy." — definiční kopula
#: (root NOUN v nominativu + nsubj + cop). Vzorek kroku 7, ale uzly
#: a hrany z něj potřebuje už krok 2.
GRAVITACE = Veta(
    "Gravitace je síla působící mezi tělesy.",
    (
        Token(id=1, form="Gravitace", lemma="gravitace", upos="NOUN",
              xpos="NNFS1-----A----",
              feats={"Case": "Nom", "Gender": "Fem", "Number": "Sing"},
              head=3, deprel="nsubj", deps=None, misc=None),
        Token(id=2, form="je", lemma="být", upos="AUX",
              xpos="VB-S---3P-AAI--",
              feats={"Aspect": "Imp", "Mood": "Ind", "Number": "Sing",
                     "Person": "3", "Polarity": "Pos", "Tense": "Pres",
                     "VerbForm": "Fin", "Voice": "Act"},
              head=3, deprel="cop", deps=None, misc=None),
        Token(id=3, form="síla", lemma="síla", upos="NOUN",
              xpos="NNFS1-----A----",
              feats={"Case": "Nom", "Gender": "Fem", "Number": "Sing"},
              head=0, deprel="root", deps=None, misc=None),
        Token(id=4, form="působící", lemma="působící", upos="ADJ",
              xpos="AGFS1-----A----",
              feats={"Aspect": "Imp", "Case": "Nom", "Gender": "Fem",
                     "Number": "Sing", "Polarity": "Pos", "Tense": "Pres",
                     "VerbForm": "Part", "Voice": "Act"},
              head=3, deprel="amod", deps=None, misc=None),
        Token(id=5, form="mezi", lemma="mezi", upos="ADP",
              xpos="RR--7----------",
              feats={"AdpType": "Prep", "Case": "Ins"},
              head=6, deprel="case", deps=None, misc=None),
        Token(id=6, form="tělesy", lemma="těleso", upos="NOUN",
              xpos="NNNP7-----A----",
              feats={"Case": "Ins", "Gender": "Neut", "Number": "Plur"},
              head=4, deprel="obl", deps=None, misc=None),
        Token(id=7, form=".", lemma=".", upos="PUNCT",
              xpos="Z:-------------", feats=None,
              head=3, deprel="punct", deps=None, misc=None),
    ))

#: „Viděl něco nového." — ADJ *nový* visí na PRON *něco*, které uzel
#: není. Vzorek pro pravidlo hrany: hrana vzniká jen mezi PŘÍMO
#: sousedícími uzly, gramatické slovo v cestě se nepřeskakuje.
NECO_NOVEHO = Veta(
    "Viděl něco nového.",
    (
        Token(id=1, form="Viděl", lemma="vidět", upos="VERB",
              xpos="VpYS----R-AAI--",
              feats={"Aspect": "Imp", "Gender": "Masc", "Number": "Sing",
                     "Polarity": "Pos", "Tense": "Past", "VerbForm": "Part",
                     "Voice": "Act"},
              head=0, deprel="root", deps=None, misc=None),
        Token(id=2, form="něco", lemma="něco", upos="PRON",
              xpos="PK--4----------",
              feats={"Animacy": "Inan", "Case": "Acc", "PronType": "Ind"},
              head=1, deprel="obj", deps=None, misc=None),
        Token(id=3, form="nového", lemma="nový", upos="ADJ",
              xpos="AANS2----1A----",
              feats={"Case": "Gen", "Degree": "Pos", "Gender": "Neut",
                     "Number": "Sing", "Polarity": "Pos"},
              head=2, deprel="nmod", deps=None, misc=None),
        Token(id=4, form=".", lemma=".", upos="PUNCT",
              xpos="Z:-------------", feats=None,
              head=1, deprel="punct", deps=None, misc=None),
    ))

#: „Tam bydlí Petr." — zájmenné příslovce *tam*. Uzel to JE: bez něj
#: se graf 2 912 vět rozejde se zmraženou přejímkou (16 074 hran).
TAM_BYDLI = Veta(
    "Tam bydlí Petr.",
    (
        Token(id=1, form="Tam", lemma="tam", upos="ADV",
              xpos="Db-------------", feats={"PronType": "Dem"},
              head=2, deprel="advmod", deps=None, misc=None),
        Token(id=2, form="bydlí", lemma="bydlet", upos="VERB",
              xpos="VB-S---3P-AAI--",
              feats={"Aspect": "Imp", "Mood": "Ind", "Number": "Sing",
                     "Person": "3", "Polarity": "Pos", "Tense": "Pres",
                     "VerbForm": "Fin", "Voice": "Act"},
              head=0, deprel="root", deps=None, misc=None),
        Token(id=3, form="Petr", lemma="Petr", upos="PROPN",
              xpos="NNMS1-----A----",
              feats={"Animacy": "Anim", "Case": "Nom", "Gender": "Masc",
                     "NameType": "Giv", "Number": "Sing"},
              head=2, deprel="nsubj", deps=None, misc=None),
        Token(id=4, form=".", lemma=".", upos="PUNCT",
              xpos="Z:-------------", feats=None,
              head=2, deprel="punct", deps=None, misc=None),
    ))

#: „Kde byl pokřtěn Ježíš?" — otázka ze zadání. Dané osy (WORD= řádků
#: bez QLEM=) jsou právě být, pokřtěný, Ježíš; *kde* nese QLEM= a mezi
#: dané osy nepatří — ptá se, netvrdí.
OTAZKA_KREST = Veta(
    "Kde byl pokřtěn Ježíš?",
    (
        Token(id=1, form="Kde", lemma="kde", upos="ADV",
              xpos="Db-------------",
              feats={"PronType": "Int,Rel"},
              head=3, deprel="advmod", deps=None, misc=None),
        Token(id=2, form="byl", lemma="být", upos="AUX",
              xpos="VpYS----R-AAI--",
              feats={"Aspect": "Imp", "Gender": "Masc", "Number": "Sing",
                     "Polarity": "Pos", "Tense": "Past", "VerbForm": "Part",
                     "Voice": "Act"},
              head=3, deprel="aux:pass", deps=None, misc=None),
        Token(id=3, form="pokřtěn", lemma="pokřtěný", upos="ADJ",
              xpos="VsYS----X-APP--",
              feats={"Aspect": "Perf", "Degree": "Pos", "Gender": "Masc",
                     "Number": "Sing", "Polarity": "Pos", "Variant": "Short",
                     "VerbForm": "Part", "Voice": "Pass"},
              head=0, deprel="root", deps=None, misc=None),
        Token(id=4, form="Ježíš", lemma="Ježíš", upos="PROPN",
              xpos="NNMS1-----A----",
              feats={"Animacy": "Anim", "Case": "Nom", "Gender": "Masc",
                     "NameType": "Giv", "Number": "Sing"},
              head=3, deprel="nsubj:pass", deps=None, misc=None),
        Token(id=5, form="?", lemma="?", upos="PUNCT",
              xpos="Z:-------------", feats=None,
              head=3, deprel="punct", deps=None, misc=None),
    ))

#: „Ježíš učil v synagoze." — druhá věta s Ježíšem, aby korpus měl
#: soupeře: pokrytí osy Ježíš je pak maximum přes věty, ne jediná věta.
SYNAGOGA = Veta(
    "Ježíš učil v synagoze.",
    (
        Token(id=1, form="Ježíš", lemma="Ježíš", upos="PROPN",
              xpos="NNMS1-----A----",
              feats={"Animacy": "Anim", "Case": "Nom", "Gender": "Masc",
                     "NameType": "Giv", "Number": "Sing"},
              head=2, deprel="nsubj", deps=None, misc=None),
        Token(id=2, form="učil", lemma="učit", upos="VERB",
              xpos="VpYS----R-AAI--",
              feats={"Aspect": "Imp", "Gender": "Masc", "Number": "Sing",
                     "Polarity": "Pos", "Tense": "Past", "VerbForm": "Part",
                     "Voice": "Act"},
              head=0, deprel="root", deps=None, misc=None),
        Token(id=3, form="v", lemma="v", upos="ADP",
              xpos="RR--6----------",
              feats={"AdpType": "Prep", "Case": "Loc"},
              head=4, deprel="case", deps=None, misc=None),
        Token(id=4, form="synagoze", lemma="synagoha", upos="NOUN",
              xpos="NNFS6-----A----",
              feats={"Case": "Loc", "Gender": "Fem", "Number": "Sing"},
              head=2, deprel="obl", deps=None, misc=None),
        Token(id=5, form=".", lemma=".", upos="PUNCT",
              xpos="Z:-------------", feats=None,
              head=2, deprel="punct", deps=None, misc=None),
    ))

#: „Muž byl ve vězení." — kopula s rootem v LOKÁLU. Definice to NENÍ:
#: říká, kde muž byl, ne co muž je. Rozdíl nese pád rootu.
VEZENI = Veta(
    "Muž byl ve vězení.",
    (
        Token(id=1, form="Muž", lemma="muž", upos="NOUN",
              xpos="NNMS1-----A----",
              feats={"Animacy": "Anim", "Case": "Nom", "Gender": "Masc",
                     "Number": "Sing"},
              head=4, deprel="nsubj", deps=None, misc=None),
        Token(id=2, form="byl", lemma="být", upos="AUX",
              xpos="VpYS----R-AAI--",
              feats={"Aspect": "Imp", "Gender": "Masc", "Number": "Sing",
                     "Polarity": "Pos", "Tense": "Past", "VerbForm": "Part",
                     "Voice": "Act"},
              head=4, deprel="cop", deps=None, misc=None),
        Token(id=3, form="ve", lemma="v", upos="ADP",
              xpos="RV--6----------",
              feats={"AdpType": "Voc", "Case": "Loc"},
              head=4, deprel="case", deps=None, misc=None),
        Token(id=4, form="vězení", lemma="vězení", upos="NOUN",
              xpos="NNNS6-----A----",
              feats={"Case": "Loc", "Gender": "Neut", "Number": "Sing"},
              head=0, deprel="root", deps=None, misc=None),
        Token(id=5, form=".", lemma=".", upos="PUNCT",
              xpos="Z:-------------", feats=None,
              head=4, deprel="punct", deps=None, misc=None),
    ))

#: „Elektromotor je stroj." — čistá definiční kopula, druhý doklad
#: vzoru (root NOUN v nominativu + nsubj + cop).
ELEKTROMOTOR = Veta(
    "Elektromotor je stroj.",
    (
        Token(id=1, form="Elektromotor", lemma="elektromotor", upos="NOUN",
              xpos="NNIS1-----A----",
              feats={"Animacy": "Inan", "Case": "Nom", "Gender": "Masc",
                     "Number": "Sing"},
              head=3, deprel="nsubj", deps=None, misc=None),
        Token(id=2, form="je", lemma="být", upos="AUX",
              xpos="VB-S---3P-AAI--",
              feats={"Aspect": "Imp", "Mood": "Ind", "Number": "Sing",
                     "Person": "3", "Polarity": "Pos", "Tense": "Pres",
                     "VerbForm": "Fin", "Voice": "Act"},
              head=3, deprel="cop", deps=None, misc=None),
        Token(id=3, form="stroj", lemma="stroj", upos="NOUN",
              xpos="NNIS1-----A----",
              feats={"Animacy": "Inan", "Case": "Nom", "Gender": "Masc",
                     "Number": "Sing"},
              head=0, deprel="root", deps=None, misc=None),
        Token(id=4, form=".", lemma=".", upos="PUNCT",
              xpos="Z:-------------", feats=None,
              head=3, deprel="punct", deps=None, misc=None),
    ))

#: „Jméno té hvězdy je Pelyněk." — definiens je VLASTNÍ jméno.
#: Kdo připustí jen NOUN v rootu, o tuhle třídu definic přijde
#: (naměřeno: 91 vazeb místo 94 na 12 258 větách).
PELYNEK = Veta(
    "Jméno té hvězdy je Pelyněk.",
    (
        Token(id=1, form="Jméno", lemma="jméno", upos="NOUN",
              xpos="NNNS1-----A----",
              feats={"Case": "Nom", "Gender": "Neut", "Number": "Sing"},
              head=5, deprel="nsubj", deps=None, misc=None),
        Token(id=2, form="té", lemma="ten", upos="DET",
              xpos="PDFS2----------",
              feats={"Case": "Gen", "Gender": "Fem", "Number": "Sing",
                     "PronType": "Dem"},
              head=3, deprel="det", deps=None, misc=None),
        Token(id=3, form="hvězdy", lemma="hvězda", upos="NOUN",
              xpos="NNFS2-----A----",
              feats={"Case": "Gen", "Gender": "Fem", "Number": "Sing"},
              head=1, deprel="nmod", deps=None, misc=None),
        Token(id=4, form="je", lemma="být", upos="AUX",
              xpos="VB-S---3P-AAI--",
              feats={"Aspect": "Imp", "Mood": "Ind", "Number": "Sing",
                     "Person": "3", "Polarity": "Pos", "Tense": "Pres",
                     "VerbForm": "Fin", "Voice": "Act"},
              head=5, deprel="cop", deps=None, misc=None),
        Token(id=5, form="Pelyněk", lemma="Pelyněk", upos="PROPN",
              xpos="NNMS1-----A----",
              feats={"Animacy": "Anim", "Case": "Nom", "Gender": "Masc",
                     "NameType": "Giv", "Number": "Sing"},
              head=0, deprel="root", deps=None, misc=None),
        Token(id=6, form=".", lemma=".", upos="PUNCT",
              xpos="Z:-------------", feats=None,
              head=5, deprel="punct", deps=None, misc=None),
    ))

#: „Trpasličí galaxie je malá galaxie." — definiční tvar, ale obě
#: strany mají TÉŽ lemma. Vazba by byla smyčka v ose (šíření by
#: aktivaci jen zesílilo samo ze sebe), takže se nezakládá.
GALAXIE = Veta(
    "Trpasličí galaxie je malá galaxie.",
    (
        Token(id=1, form="Trpasličí", lemma="trpasličí", upos="ADJ",
              xpos="AAFS1----1A----",
              feats={"Case": "Nom", "Degree": "Pos", "Gender": "Fem",
                     "Number": "Sing", "Polarity": "Pos"},
              head=2, deprel="amod", deps=None, misc=None),
        Token(id=2, form="galaxie", lemma="galaxie", upos="NOUN",
              xpos="NNFS1-----A----",
              feats={"Case": "Nom", "Gender": "Fem", "Number": "Sing"},
              head=5, deprel="nsubj", deps=None, misc=None),
        Token(id=3, form="je", lemma="být", upos="AUX",
              xpos="VB-S---3P-AAI--",
              feats={"Aspect": "Imp", "Mood": "Ind", "Number": "Sing",
                     "Person": "3", "Polarity": "Pos", "Tense": "Pres",
                     "VerbForm": "Fin", "Voice": "Act"},
              head=5, deprel="cop", deps=None, misc=None),
        Token(id=4, form="malá", lemma="malý", upos="ADJ",
              xpos="AAFS1----1A----",
              feats={"Case": "Nom", "Degree": "Pos", "Gender": "Fem",
                     "Number": "Sing", "Polarity": "Pos"},
              head=5, deprel="amod", deps=None, misc=None),
        Token(id=5, form="galaxie", lemma="galaxie", upos="NOUN",
              xpos="NNFS1-----A----",
              feats={"Case": "Nom", "Gender": "Fem", "Number": "Sing"},
              head=0, deprel="root", deps=None, misc=None),
        Token(id=6, form=".", lemma=".", upos="PUNCT",
              xpos="Z:-------------", feats=None,
              head=5, deprel="punct", deps=None, misc=None),
    ))
