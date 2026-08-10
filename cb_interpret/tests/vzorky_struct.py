"""Zmražené rozbory pro strukturní extrakci (UDPipe 2026-08-10)."""
from cb_udpipe import Token


AUTO_PROSTREDEK = (  # Auto je dopravní prostředek.
    Token(id=1, form='Auto', lemma='auto', upos='NOUN', xpos='NNNS1-----A----', feats={'Case': 'Nom', 'Gender': 'Neut', 'Number': 'Sing'}, head=4, deprel='nsubj', deps=None, misc=None),
    Token(id=2, form='je', lemma='být', upos='AUX', xpos='VB-S---3P-AAI--', feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing', 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres', 'VerbForm': 'Fin', 'Voice': 'Act'}, head=4, deprel='cop', deps=None, misc=None),
    Token(id=3, form='dopravní', lemma='dopravní', upos='ADJ', xpos='AAIS1----1A----', feats={'Animacy': 'Inan', 'Case': 'Nom', 'Degree': 'Pos', 'Gender': 'Masc', 'Number': 'Sing', 'Polarity': 'Pos'}, head=4, deprel='amod', deps=None, misc=None),
    Token(id=4, form='prostředek', lemma='prostředek', upos='NOUN', xpos='NNIS1-----A----', feats={'Animacy': 'Inan', 'Case': 'Nom', 'Gender': 'Masc', 'Number': 'Sing'}, head=0, deprel='root', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=5, form='.', lemma='.', upos='PUNCT', xpos='Z:-------------', feats=None, head=4, deprel='punct', deps=None, misc={'SpaceAfter': 'No'}),
)

SILNICE_CESTA = (  # Silnice je cesta pro vozidla.
    Token(id=1, form='Silnice', lemma='silnice', upos='NOUN', xpos='NNFS1-----A----', feats={'Case': 'Nom', 'Gender': 'Fem', 'Number': 'Sing'}, head=3, deprel='nsubj', deps=None, misc=None),
    Token(id=2, form='je', lemma='být', upos='AUX', xpos='VB-S---3P-AAI--', feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing', 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres', 'VerbForm': 'Fin', 'Voice': 'Act'}, head=3, deprel='cop', deps=None, misc=None),
    Token(id=3, form='cesta', lemma='cesta', upos='NOUN', xpos='NNFS1-----A----', feats={'Case': 'Nom', 'Gender': 'Fem', 'Number': 'Sing'}, head=0, deprel='root', deps=None, misc=None),
    Token(id=4, form='pro', lemma='pro', upos='ADP', xpos='RR--4----------', feats={'AdpType': 'Prep', 'Case': 'Acc'}, head=5, deprel='case', deps=None, misc=None),
    Token(id=5, form='vozidla', lemma='vozidlo', upos='NOUN', xpos='NNNP4-----A----', feats={'Case': 'Acc', 'Gender': 'Neut', 'Number': 'Plur'}, head=3, deprel='nmod', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=6, form='.', lemma='.', upos='PUNCT', xpos='Z:-------------', feats=None, head=3, deprel='punct', deps=None, misc={'SpaceAfter': 'No'}),
)

PETR_ZKUSENY = (  # Petr je zkušený programátor.
    Token(id=1, form='Petr', lemma='Petr', upos='PROPN', xpos='NNMS1-----A----', feats={'Animacy': 'Anim', 'Case': 'Nom', 'Gender': 'Masc', 'NameType': 'Giv', 'Number': 'Sing'}, head=4, deprel='nsubj', deps=None, misc=None),
    Token(id=2, form='je', lemma='být', upos='AUX', xpos='VB-S---3P-AAI--', feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing', 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres', 'VerbForm': 'Fin', 'Voice': 'Act'}, head=4, deprel='cop', deps=None, misc=None),
    Token(id=3, form='zkušený', lemma='zkušený', upos='ADJ', xpos='AAMS1----1A----', feats={'Animacy': 'Anim', 'Case': 'Nom', 'Degree': 'Pos', 'Gender': 'Masc', 'Number': 'Sing', 'Polarity': 'Pos'}, head=4, deprel='amod', deps=None, misc=None),
    Token(id=4, form='programátor', lemma='programátor', upos='NOUN', xpos='NNMS1-----A----', feats={'Animacy': 'Anim', 'Case': 'Nom', 'Gender': 'Masc', 'Number': 'Sing'}, head=0, deprel='root', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=5, form='.', lemma='.', upos='PUNCT', xpos='Z:-------------', feats=None, head=4, deprel='punct', deps=None, misc={'SpaceAfter': 'No'}),
)

JE_AUTO_PROSTREDEK = (  # Je auto dopravní prostředek?
    Token(id=1, form='Je', lemma='být', upos='AUX', xpos='VB-S---3P-AAI--', feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing', 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres', 'VerbForm': 'Fin', 'Voice': 'Act'}, head=4, deprel='cop', deps=None, misc=None),
    Token(id=2, form='auto', lemma='auto', upos='NOUN', xpos='NNNS1-----A----', feats={'Case': 'Nom', 'Gender': 'Neut', 'Number': 'Sing'}, head=4, deprel='nsubj', deps=None, misc=None),
    Token(id=3, form='dopravní', lemma='dopravní', upos='ADJ', xpos='AAIS1----1A----', feats={'Animacy': 'Inan', 'Case': 'Nom', 'Degree': 'Pos', 'Gender': 'Masc', 'Number': 'Sing', 'Polarity': 'Pos'}, head=4, deprel='amod', deps=None, misc=None),
    Token(id=4, form='prostředek', lemma='prostředek', upos='NOUN', xpos='NNIS1-----A----', feats={'Animacy': 'Inan', 'Case': 'Nom', 'Gender': 'Masc', 'Number': 'Sing'}, head=0, deprel='root', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=5, form='?', lemma='?', upos='PUNCT', xpos='Z:-------------', feats=None, head=4, deprel='punct', deps=None, misc={'SpaceAfter': 'No'}),
)

KNIHA_DAREK = (  # Kniha je dárek pro Petra.
    Token(id=1, form='Kniha', lemma='kniha', upos='NOUN', xpos='NNFS1-----A----', feats={'Case': 'Nom', 'Gender': 'Fem', 'Number': 'Sing'}, head=3, deprel='nsubj', deps=None, misc=None),
    Token(id=2, form='je', lemma='být', upos='AUX', xpos='VB-S---3P-AAI--', feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing', 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres', 'VerbForm': 'Fin', 'Voice': 'Act'}, head=3, deprel='cop', deps=None, misc=None),
    Token(id=3, form='dárek', lemma='dárek', upos='NOUN', xpos='NNIS1-----A----', feats={'Animacy': 'Inan', 'Case': 'Nom', 'Gender': 'Masc', 'Number': 'Sing'}, head=0, deprel='root', deps=None, misc=None),
    Token(id=4, form='pro', lemma='pro', upos='ADP', xpos='RR--4----------', feats={'AdpType': 'Prep', 'Case': 'Acc'}, head=5, deprel='case', deps=None, misc=None),
    Token(id=5, form='Petra', lemma='Petr', upos='PROPN', xpos='NNMS4-----A----', feats={'Animacy': 'Anim', 'Case': 'Acc', 'Gender': 'Masc', 'NameType': 'Giv', 'Number': 'Sing'}, head=3, deprel='nmod', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=6, form='.', lemma='.', upos='PUNCT', xpos='Z:-------------', feats=None, head=3, deprel='punct', deps=None, misc={'SpaceAfter': 'No'}),
)

PES_DOMACI = (  # Pes je domácí zvíře.
    Token(id=1, form='Pes', lemma='pes', upos='NOUN', xpos='NNMS1-----A----', feats={'Animacy': 'Anim', 'Case': 'Nom', 'Gender': 'Masc', 'Number': 'Sing'}, head=4, deprel='nsubj', deps=None, misc=None),
    Token(id=2, form='je', lemma='být', upos='AUX', xpos='VB-S---3P-AAI--', feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing', 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres', 'VerbForm': 'Fin', 'Voice': 'Act'}, head=4, deprel='cop', deps=None, misc=None),
    Token(id=3, form='domácí', lemma='domácí', upos='ADJ', xpos='AANS1----1A----', feats={'Case': 'Nom', 'Degree': 'Pos', 'Gender': 'Neut', 'Number': 'Sing', 'Polarity': 'Pos'}, head=4, deprel='amod', deps=None, misc=None),
    Token(id=4, form='zvíře', lemma='zvíře', upos='NOUN', xpos='NNNS1-----A----', feats={'Case': 'Nom', 'Gender': 'Neut', 'Number': 'Sing'}, head=0, deprel='root', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=5, form='.', lemma='.', upos='PUNCT', xpos='Z:-------------', feats=None, head=4, deprel='punct', deps=None, misc={'SpaceAfter': 'No'}),
)

JE_PETR_ZKUSENY = (  # Je Petr zkušený programátor?
    Token(id=1, form='Je', lemma='být', upos='AUX', xpos='VB-S---3P-AAI--', feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing', 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres', 'VerbForm': 'Fin', 'Voice': 'Act'}, head=4, deprel='cop', deps=None, misc=None),
    Token(id=2, form='Petr', lemma='Petr', upos='PROPN', xpos='NNMS1-----A----', feats={'Animacy': 'Anim', 'Case': 'Nom', 'Gender': 'Masc', 'NameType': 'Giv', 'Number': 'Sing'}, head=4, deprel='nsubj', deps=None, misc=None),
    Token(id=3, form='zkušený', lemma='zkušený', upos='ADJ', xpos='AAMS1----1A----', feats={'Animacy': 'Anim', 'Case': 'Nom', 'Degree': 'Pos', 'Gender': 'Masc', 'Number': 'Sing', 'Polarity': 'Pos'}, head=4, deprel='amod', deps=None, misc=None),
    Token(id=4, form='programátor', lemma='programátor', upos='NOUN', xpos='NNMS1-----A----', feats={'Animacy': 'Anim', 'Case': 'Nom', 'Gender': 'Masc', 'Number': 'Sing'}, head=0, deprel='root', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=5, form='?', lemma='?', upos='PUNCT', xpos='Z:-------------', feats=None, head=4, deprel='punct', deps=None, misc={'SpaceAfter': 'No'}),
)
