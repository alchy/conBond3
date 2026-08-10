"""Zmražené rozbory UDPipe 2 pro testy interpretace.

Hodnoty jsou skutečné výstupy služby cb-udpipe (model cs_all-ud-2.17,
tokenizér 6247b8b7a5c8, pořízeno 2026-08-09) — testy nesmí potřebovat
běžící službu (politika § 13). Kdo je mění, mění zemní pravdu testů.
"""
from cb_udpipe import Token

# Vygenerováno z UDPipe 2 (model cs_all-ud-2.17, tokenizér 6247b8b7a5c8).

PETR_PROGRAMATOR = (  # Petr je programátor.
    Token(id=1, form='Petr', lemma='Petr', upos='PROPN', xpos='NNMS1-----A----', feats={'Animacy': 'Anim', 'Case': 'Nom', 'Gender': 'Masc', 'NameType': 'Giv', 'Number': 'Sing'}, head=3, deprel='nsubj', deps=None, misc=None),
    Token(id=2, form='je', lemma='být', upos='AUX', xpos='VB-S---3P-AAI--', feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing', 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres', 'VerbForm': 'Fin', 'Voice': 'Act'}, head=3, deprel='cop', deps=None, misc=None),
    Token(id=3, form='programátor', lemma='programátor', upos='NOUN', xpos='NNMS1-----A----', feats={'Animacy': 'Anim', 'Case': 'Nom', 'Gender': 'Masc', 'Number': 'Sing'}, head=0, deprel='root', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=4, form='.', lemma='.', upos='PUNCT', xpos='Z:-------------', feats=None, head=3, deprel='punct', deps=None, misc={'SpaceAfter': 'No'}),
)

PETR_NENI_STUDENT = (  # Petr není student.
    Token(id=1, form='Petr', lemma='Petr', upos='PROPN', xpos='NNMS1-----A----', feats={'Animacy': 'Anim', 'Case': 'Nom', 'Gender': 'Masc', 'NameType': 'Giv', 'Number': 'Sing'}, head=3, deprel='nsubj', deps=None, misc=None),
    Token(id=2, form='není', lemma='být', upos='AUX', xpos='VB-S---3P-NAI--', feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing', 'Person': '3', 'Polarity': 'Neg', 'Tense': 'Pres', 'VerbForm': 'Fin', 'Voice': 'Act'}, head=3, deprel='cop', deps=None, misc=None),
    Token(id=3, form='student', lemma='student', upos='NOUN', xpos='NNMS1-----A----', feats={'Animacy': 'Anim', 'Case': 'Nom', 'Gender': 'Masc', 'Number': 'Sing'}, head=0, deprel='root', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=4, form='.', lemma='.', upos='PUNCT', xpos='Z:-------------', feats=None, head=3, deprel='punct', deps=None, misc={'SpaceAfter': 'No'}),
)

KAZDY_PROGRAMATOR = (  # Každý programátor je člověk.
    Token(id=1, form='Každý', lemma='každý', upos='DET', xpos='PLMS1----------', feats={'Animacy': 'Anim', 'Case': 'Nom', 'Gender': 'Masc', 'Number': 'Sing', 'PronType': 'Tot'}, head=2, deprel='det', deps=None, misc=None),
    Token(id=2, form='programátor', lemma='programátor', upos='NOUN', xpos='NNMS1-----A----', feats={'Animacy': 'Anim', 'Case': 'Nom', 'Gender': 'Masc', 'Number': 'Sing'}, head=4, deprel='nsubj', deps=None, misc=None),
    Token(id=3, form='je', lemma='být', upos='AUX', xpos='VB-S---3P-AAI--', feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing', 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres', 'VerbForm': 'Fin', 'Voice': 'Act'}, head=4, deprel='cop', deps=None, misc=None),
    Token(id=4, form='člověk', lemma='člověk', upos='NOUN', xpos='NNMS1-----A----', feats={'Animacy': 'Anim', 'Case': 'Nom', 'Gender': 'Masc', 'Number': 'Sing'}, head=0, deprel='root', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=5, form='.', lemma='.', upos='PUNCT', xpos='Z:-------------', feats=None, head=4, deprel='punct', deps=None, misc={'SpaceAfter': 'No'}),
)

ZADNY_PTAK = (  # Žádný pták není savec.
    Token(id=1, form='Žádný', lemma='žádný', upos='DET', xpos='PWYS1----------', feats={'Case': 'Nom', 'Gender': 'Masc', 'Number': 'Sing', 'PronType': 'Neg'}, head=2, deprel='det', deps=None, misc=None),
    Token(id=2, form='pták', lemma='pták', upos='NOUN', xpos='NNMS1-----A----', feats={'Animacy': 'Anim', 'Case': 'Nom', 'Gender': 'Masc', 'Number': 'Sing'}, head=4, deprel='nsubj', deps=None, misc=None),
    Token(id=3, form='není', lemma='být', upos='AUX', xpos='VB-S---3P-NAI--', feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing', 'Person': '3', 'Polarity': 'Neg', 'Tense': 'Pres', 'VerbForm': 'Fin', 'Voice': 'Act'}, head=4, deprel='cop', deps=None, misc=None),
    Token(id=4, form='savec', lemma='savec', upos='NOUN', xpos='NNMS1-----A----', feats={'Animacy': 'Anim', 'Case': 'Nom', 'Gender': 'Masc', 'Number': 'Sing'}, head=0, deprel='root', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=5, form='.', lemma='.', upos='PUNCT', xpos='Z:-------------', feats=None, head=4, deprel='punct', deps=None, misc={'SpaceAfter': 'No'}),
)

PES_SAVEC = (  # Pes je savec.
    Token(id=1, form='Pes', lemma='pes', upos='NOUN', xpos='NNMS1-----A----', feats={'Animacy': 'Anim', 'Case': 'Nom', 'Gender': 'Masc', 'Number': 'Sing'}, head=3, deprel='nsubj', deps=None, misc=None),
    Token(id=2, form='je', lemma='být', upos='AUX', xpos='VB-S---3P-AAI--', feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing', 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres', 'VerbForm': 'Fin', 'Voice': 'Act'}, head=3, deprel='cop', deps=None, misc=None),
    Token(id=3, form='savec', lemma='savec', upos='NOUN', xpos='NNMS1-----A----', feats={'Animacy': 'Anim', 'Case': 'Nom', 'Gender': 'Masc', 'Number': 'Sing'}, head=0, deprel='root', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=4, form='.', lemma='.', upos='PUNCT', xpos='Z:-------------', feats=None, head=3, deprel='punct', deps=None, misc={'SpaceAfter': 'No'}),
)

JE_PETR_CLOVEK = (  # Je Petr člověk?
    Token(id=1, form='Je', lemma='být', upos='AUX', xpos='VB-S---3P-AAI--', feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing', 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres', 'VerbForm': 'Fin', 'Voice': 'Act'}, head=3, deprel='cop', deps=None, misc=None),
    Token(id=2, form='Petr', lemma='Petr', upos='PROPN', xpos='NNMS1-----A----', feats={'Animacy': 'Anim', 'Case': 'Nom', 'Gender': 'Masc', 'NameType': 'Giv', 'Number': 'Sing'}, head=3, deprel='nsubj', deps=None, misc=None),
    Token(id=3, form='člověk', lemma='člověk', upos='NOUN', xpos='NNMS1-----A----', feats={'Animacy': 'Anim', 'Case': 'Nom', 'Gender': 'Masc', 'Number': 'Sing'}, head=0, deprel='root', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=4, form='?', lemma='?', upos='PUNCT', xpos='Z:-------------', feats=None, head=3, deprel='punct', deps=None, misc={'SpaceAfter': 'No'}),
)

PETR_BYDLI = (  # Petr bydlí v Praze.
    Token(id=1, form='Petr', lemma='Petr', upos='PROPN', xpos='NNMS1-----A----', feats={'Animacy': 'Anim', 'Case': 'Nom', 'Gender': 'Masc', 'NameType': 'Giv', 'Number': 'Sing'}, head=2, deprel='nsubj', deps=None, misc=None),
    Token(id=2, form='bydlí', lemma='bydlet', upos='VERB', xpos='VB-S---3P-AAI--', feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing', 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres', 'VerbForm': 'Fin', 'Voice': 'Act'}, head=0, deprel='root', deps=None, misc=None),
    Token(id=3, form='v', lemma='v', upos='ADP', xpos='RR--6----------', feats={'AdpType': 'Prep', 'Case': 'Loc'}, head=4, deprel='case', deps=None, misc=None),
    Token(id=4, form='Praze', lemma='Praha', upos='PROPN', xpos='NNFS6-----A----', feats={'Case': 'Loc', 'Gender': 'Fem', 'NameType': 'Geo', 'Number': 'Sing'}, head=2, deprel='obl', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=5, form='.', lemma='.', upos='PUNCT', xpos='Z:-------------', feats=None, head=2, deprel='punct', deps=None, misc={'SpaceAfter': 'No'}),
)

PETR_ZNA = (  # Petr zná Janu.
    Token(id=1, form='Petr', lemma='Petr', upos='PROPN', xpos='NNMS1-----A----', feats={'Animacy': 'Anim', 'Case': 'Nom', 'Gender': 'Masc', 'NameType': 'Giv', 'Number': 'Sing'}, head=2, deprel='nsubj', deps=None, misc=None),
    Token(id=2, form='zná', lemma='znát', upos='VERB', xpos='VB-S---3P-AAI--', feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing', 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres', 'VerbForm': 'Fin', 'Voice': 'Act'}, head=0, deprel='root', deps=None, misc=None),
    Token(id=3, form='Janu', lemma='Jana', upos='PROPN', xpos='NNFS4-----A----', feats={'Case': 'Acc', 'Gender': 'Fem', 'NameType': 'Giv', 'Number': 'Sing'}, head=2, deprel='obj', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=4, form='.', lemma='.', upos='PUNCT', xpos='Z:-------------', feats=None, head=2, deprel='punct', deps=None, misc={'SpaceAfter': 'No'}),
)

SLUNCE_SVITI = (  # Slunce svítí.
    Token(id=1, form='Slunce', lemma='slunce', upos='NOUN', xpos='NNNS1-----A----', feats={'Case': 'Nom', 'Gender': 'Neut', 'Number': 'Sing'}, head=2, deprel='nsubj', deps=None, misc=None),
    Token(id=2, form='svítí', lemma='svítit', upos='VERB', xpos='VB-S---3P-AAI--', feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing', 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres', 'VerbForm': 'Fin', 'Voice': 'Act'}, head=0, deprel='root', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=3, form='.', lemma='.', upos='PUNCT', xpos='Z:-------------', feats=None, head=2, deprel='punct', deps=None, misc={'SpaceAfter': 'No'}),
)

KOLIK_HODIN = (  # Kolik je hodin?
    Token(id=1, form='Kolik', lemma='kolik', upos='DET', xpos='Ca--1----------', feats={'Case': 'Nom', 'NumType': 'Card', 'PronType': 'Dem,Ind'}, head=3, deprel='det:numgov', deps=None, misc=None),
    Token(id=2, form='je', lemma='být', upos='AUX', xpos='VB-S---3P-AAI--', feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing', 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres', 'VerbForm': 'Fin', 'Voice': 'Act'}, head=0, deprel='root', deps=None, misc=None),
    Token(id=3, form='hodin', lemma='hodina', upos='NOUN', xpos='NNFP2-----A----', feats={'Case': 'Gen', 'Gender': 'Fem', 'Number': 'Plur'}, head=2, deprel='nsubj', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=4, form='?', lemma='?', upos='PUNCT', xpos='Z:-------------', feats=None, head=2, deprel='punct', deps=None, misc={'SpaceAfter': 'No'}),
)

VSICHNI_PROGRAMATORI = (  # Všichni programátoři jsou lidé.
    Token(id=1, form='Všichni', lemma='všechen', upos='DET', xpos='PLMP1----------', feats={'Animacy': 'Anim', 'Case': 'Nom', 'Gender': 'Masc', 'Number': 'Plur', 'PronType': 'Tot'}, head=2, deprel='det', deps=None, misc=None),
    Token(id=2, form='programátoři', lemma='programátor', upos='NOUN', xpos='NNMP1-----A----', feats={'Animacy': 'Anim', 'Case': 'Nom', 'Gender': 'Masc', 'Number': 'Plur'}, head=4, deprel='nsubj', deps=None, misc=None),
    Token(id=3, form='jsou', lemma='být', upos='AUX', xpos='VB-P---3P-AAI--', feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Plur', 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres', 'VerbForm': 'Fin', 'Voice': 'Act'}, head=4, deprel='cop', deps=None, misc=None),
    Token(id=4, form='lidé', lemma='lidé', upos='NOUN', xpos='NNMP1-----A----', feats={'Animacy': 'Anim', 'Case': 'Nom', 'Gender': 'Masc', 'Number': 'Plur'}, head=0, deprel='root', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=5, form='.', lemma='.', upos='PUNCT', xpos='Z:-------------', feats=None, head=4, deprel='punct', deps=None, misc={'SpaceAfter': 'No'}),
)
