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

PETR_JEDE_AUTEM = (  # Petr jede autem po dálnici.
    Token(id=1, form='Petr', lemma='Petr', upos='PROPN', xpos='NNMS1-----A----', feats={'Animacy': 'Anim', 'Case': 'Nom', 'Gender': 'Masc', 'NameType': 'Giv', 'Number': 'Sing'}, head=2, deprel='nsubj', deps=None, misc=None),
    Token(id=2, form='jede', lemma='jet', upos='VERB', xpos='VB-S---3P-AAI--', feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing', 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres', 'VerbForm': 'Fin', 'Voice': 'Act'}, head=0, deprel='root', deps=None, misc=None),
    Token(id=3, form='autem', lemma='auto', upos='NOUN', xpos='NNNS7-----A----', feats={'Case': 'Ins', 'Gender': 'Neut', 'Number': 'Sing'}, head=2, deprel='obl', deps=None, misc=None),
    Token(id=4, form='po', lemma='po', upos='ADP', xpos='RR--6----------', feats={'AdpType': 'Prep', 'Case': 'Loc'}, head=5, deprel='case', deps=None, misc=None),
    Token(id=5, form='dálnici', lemma='dálnice', upos='NOUN', xpos='NNFS6-----A----', feats={'Case': 'Loc', 'Gender': 'Fem', 'Number': 'Sing'}, head=2, deprel='obl', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=6, form='.', lemma='.', upos='PUNCT', xpos='Z:-------------', feats=None, head=2, deprel='punct', deps=None, misc={'SpaceAfter': 'No'}),
)

JEDE_PETR_AUTEM = (  # Jede Petr autem po dálnici?
    Token(id=1, form='Jede', lemma='jet', upos='VERB', xpos='VB-S---3P-AAI--', feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing', 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres', 'VerbForm': 'Fin', 'Voice': 'Act'}, head=0, deprel='root', deps=None, misc=None),
    Token(id=2, form='Petr', lemma='Petr', upos='PROPN', xpos='NNMS1-----A----', feats={'Animacy': 'Anim', 'Case': 'Nom', 'Gender': 'Masc', 'NameType': 'Giv', 'Number': 'Sing'}, head=1, deprel='nsubj', deps=None, misc=None),
    Token(id=3, form='autem', lemma='auto', upos='NOUN', xpos='NNNS7-----A----', feats={'Case': 'Ins', 'Gender': 'Neut', 'Number': 'Sing'}, head=1, deprel='obl', deps=None, misc=None),
    Token(id=4, form='po', lemma='po', upos='ADP', xpos='RR--6----------', feats={'AdpType': 'Prep', 'Case': 'Loc'}, head=5, deprel='case', deps=None, misc=None),
    Token(id=5, form='dálnici', lemma='dálnice', upos='NOUN', xpos='NNFS6-----A----', feats={'Case': 'Loc', 'Gender': 'Fem', 'Number': 'Sing'}, head=1, deprel='obl', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=6, form='?', lemma='?', upos='PUNCT', xpos='Z:-------------', feats=None, head=1, deprel='punct', deps=None, misc={'SpaceAfter': 'No'}),
)

PETR_RYCHLE_JEDE = (  # Petr rychle jede po dálnici.
    Token(id=1, form='Petr', lemma='Petr', upos='PROPN', xpos='NNMS1-----A----', feats={'Animacy': 'Anim', 'Case': 'Nom', 'Gender': 'Masc', 'NameType': 'Giv', 'Number': 'Sing'}, head=3, deprel='nsubj', deps=None, misc=None),
    Token(id=2, form='rychle', lemma='rychle', upos='ADV', xpos='Dg-------1A----', feats={'Degree': 'Pos', 'Polarity': 'Pos'}, head=3, deprel='advmod', deps=None, misc=None),
    Token(id=3, form='jede', lemma='jet', upos='VERB', xpos='VB-S---3P-AAI--', feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing', 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres', 'VerbForm': 'Fin', 'Voice': 'Act'}, head=0, deprel='root', deps=None, misc=None),
    Token(id=4, form='po', lemma='po', upos='ADP', xpos='RR--6----------', feats={'AdpType': 'Prep', 'Case': 'Loc'}, head=5, deprel='case', deps=None, misc=None),
    Token(id=5, form='dálnici', lemma='dálnice', upos='NOUN', xpos='NNFS6-----A----', feats={'Case': 'Loc', 'Gender': 'Fem', 'Number': 'Sing'}, head=3, deprel='obl', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=6, form='.', lemma='.', upos='PUNCT', xpos='Z:-------------', feats=None, head=3, deprel='punct', deps=None, misc={'SpaceAfter': 'No'}),
)

PETR_DAL_PAVLOVI = (  # Petr dal Pavlovi knihu.
    Token(id=1, form='Petr', lemma='Petr', upos='PROPN', xpos='NNMS1-----A----', feats={'Animacy': 'Anim', 'Case': 'Nom', 'Gender': 'Masc', 'NameType': 'Giv', 'Number': 'Sing'}, head=2, deprel='nsubj', deps=None, misc=None),
    Token(id=2, form='dal', lemma='dát', upos='VERB', xpos='VpYS----R-AAP--', feats={'Aspect': 'Perf', 'Gender': 'Masc', 'Number': 'Sing', 'Polarity': 'Pos', 'Tense': 'Past', 'VerbForm': 'Part', 'Voice': 'Act'}, head=0, deprel='root', deps=None, misc=None),
    Token(id=3, form='Pavlovi', lemma='Pavel', upos='PROPN', xpos='NNMS3-----A----', feats={'Animacy': 'Anim', 'Case': 'Dat', 'Gender': 'Masc', 'NameType': 'Giv', 'Number': 'Sing'}, head=2, deprel='obl:arg', deps=None, misc=None),
    Token(id=4, form='knihu', lemma='kniha', upos='NOUN', xpos='NNFS4-----A----', feats={'Case': 'Acc', 'Gender': 'Fem', 'Number': 'Sing'}, head=2, deprel='obj', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=5, form='.', lemma='.', upos='PUNCT', xpos='Z:-------------', feats=None, head=2, deprel='punct', deps=None, misc={'SpaceAfter': 'No'}),
)

PETR_RIDI_AUTO = (  # Petr řídí červené auto.
    Token(id=1, form='Petr', lemma='Petr', upos='PROPN', xpos='NNMS1-----A----', feats={'Animacy': 'Anim', 'Case': 'Nom', 'Gender': 'Masc', 'NameType': 'Giv', 'Number': 'Sing'}, head=2, deprel='nsubj', deps=None, misc=None),
    Token(id=2, form='řídí', lemma='řídit', upos='VERB', xpos='VB-S---3P-AAI--', feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing', 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres', 'VerbForm': 'Fin', 'Voice': 'Act'}, head=0, deprel='root', deps=None, misc=None),
    Token(id=3, form='červené', lemma='červený', upos='ADJ', xpos='AANS4----1A----', feats={'Case': 'Acc', 'Degree': 'Pos', 'Gender': 'Neut', 'Number': 'Sing', 'Polarity': 'Pos'}, head=4, deprel='amod', deps=None, misc=None),
    Token(id=4, form='auto', lemma='auto', upos='NOUN', xpos='NNNS4-----A----', feats={'Case': 'Acc', 'Gender': 'Neut', 'Number': 'Sing'}, head=2, deprel='obj', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=5, form='.', lemma='.', upos='PUNCT', xpos='Z:-------------', feats=None, head=2, deprel='punct', deps=None, misc={'SpaceAfter': 'No'}),
)

MARIE_PRACUJE = (  # Marie pracuje v Brně.   (generalizace — unseen)
    Token(id=1, form='Marie', lemma='Marie', upos='PROPN', xpos='NNFS1-----A----', feats={'Case': 'Nom', 'Gender': 'Fem', 'NameType': 'Giv', 'Number': 'Sing'}, head=2, deprel='nsubj', deps=None, misc=None),
    Token(id=2, form='pracuje', lemma='pracovat', upos='VERB', xpos='VB-S---3P-AAI--', feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing', 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres', 'VerbForm': 'Fin', 'Voice': 'Act'}, head=0, deprel='root', deps=None, misc=None),
    Token(id=3, form='v', lemma='v', upos='ADP', xpos='RR--6----------', feats={'AdpType': 'Prep', 'Case': 'Loc'}, head=4, deprel='case', deps=None, misc=None),
    Token(id=4, form='Brně', lemma='Brno', upos='PROPN', xpos='NNNS6-----A----', feats={'Case': 'Loc', 'Gender': 'Neut', 'NameType': 'Geo', 'Number': 'Sing'}, head=2, deprel='obl', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=5, form='.', lemma='.', upos='PUNCT', xpos='Z:-------------', feats=None, head=2, deprel='punct', deps=None, misc={'SpaceAfter': 'No'}),
)

AUTO_MUZE_JET_DO_MESTA = (  # Auto může jet po dálnici do města.
    Token(id=1, form='Auto', lemma='auto', upos='NOUN', xpos='NNNS1-----A----', feats={'Case': 'Nom', 'Gender': 'Neut', 'Number': 'Sing'}, head=2, deprel='nsubj', deps=None, misc=None),
    Token(id=2, form='může', lemma='moci', upos='VERB', xpos='VB-S---3P-AAI--', feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing', 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres', 'VerbForm': 'Fin', 'Voice': 'Act'}, head=0, deprel='root', deps=None, misc=None),
    Token(id=3, form='jet', lemma='jet', upos='VERB', xpos='Vf--------A-I--', feats={'Aspect': 'Imp', 'Polarity': 'Pos', 'VerbForm': 'Inf'}, head=2, deprel='xcomp', deps=None, misc=None),
    Token(id=4, form='po', lemma='po', upos='ADP', xpos='RR--6----------', feats={'AdpType': 'Prep', 'Case': 'Loc'}, head=5, deprel='case', deps=None, misc=None),
    Token(id=5, form='dálnici', lemma='dálnice', upos='NOUN', xpos='NNFS6-----A----', feats={'Case': 'Loc', 'Gender': 'Fem', 'Number': 'Sing'}, head=3, deprel='obl', deps=None, misc=None),
    Token(id=6, form='do', lemma='do', upos='ADP', xpos='RR--2----------', feats={'AdpType': 'Prep', 'Case': 'Gen'}, head=7, deprel='case', deps=None, misc=None),
    Token(id=7, form='města', lemma='město', upos='NOUN', xpos='NNNS2-----A----', feats={'Case': 'Gen', 'Gender': 'Neut', 'Number': 'Sing'}, head=3, deprel='obl', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=8, form='.', lemma='.', upos='PUNCT', xpos='Z:-------------', feats=None, head=2, deprel='punct', deps=None, misc={'SpaceAfter': 'No'}),
)

PRAHA_MESTO_CESKA = (  # Praha je hlavní město Česka.
    Token(id=1, form='Praha', lemma='Praha', upos='PROPN', xpos='NNFS1-----A----', feats={'Case': 'Nom', 'Gender': 'Fem', 'NameType': 'Geo', 'Number': 'Sing'}, head=4, deprel='nsubj', deps=None, misc=None),
    Token(id=2, form='je', lemma='být', upos='AUX', xpos='VB-S---3P-AAI--', feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing', 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres', 'VerbForm': 'Fin', 'Voice': 'Act'}, head=4, deprel='cop', deps=None, misc=None),
    Token(id=3, form='hlavní', lemma='hlavní', upos='ADJ', xpos='AANS1----1A----', feats={'Case': 'Nom', 'Degree': 'Pos', 'Gender': 'Neut', 'Number': 'Sing', 'Polarity': 'Pos'}, head=4, deprel='amod', deps=None, misc=None),
    Token(id=4, form='město', lemma='město', upos='NOUN', xpos='NNNS1-----A----', feats={'Case': 'Nom', 'Gender': 'Neut', 'Number': 'Sing'}, head=0, deprel='root', deps=None, misc=None),
    Token(id=5, form='Česka', lemma='Česko', upos='PROPN', xpos='NNNS2-----A----', feats={'Case': 'Gen', 'Gender': 'Neut', 'NameType': 'Geo', 'Number': 'Sing'}, head=4, deprel='nmod', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=6, form='.', lemma='.', upos='PUNCT', xpos='Z:-------------', feats=None, head=4, deprel='punct', deps=None, misc={'SpaceAfter': 'No'}),
)

JE_PRAHA_MESTO_CESKA = (  # Je Praha hlavní město Česka?
    Token(id=1, form='Je', lemma='být', upos='AUX', xpos='VB-S---3P-AAI--', feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing', 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres', 'VerbForm': 'Fin', 'Voice': 'Act'}, head=4, deprel='cop', deps=None, misc=None),
    Token(id=2, form='Praha', lemma='Praha', upos='PROPN', xpos='NNFS1-----A----', feats={'Case': 'Nom', 'Gender': 'Fem', 'NameType': 'Geo', 'Number': 'Sing'}, head=4, deprel='nsubj', deps=None, misc=None),
    Token(id=3, form='hlavní', lemma='hlavní', upos='ADJ', xpos='AANS1----1A----', feats={'Case': 'Nom', 'Degree': 'Pos', 'Gender': 'Neut', 'Number': 'Sing', 'Polarity': 'Pos'}, head=4, deprel='amod', deps=None, misc=None),
    Token(id=4, form='město', lemma='město', upos='NOUN', xpos='NNNS1-----A----', feats={'Case': 'Nom', 'Gender': 'Neut', 'Number': 'Sing'}, head=0, deprel='root', deps=None, misc=None),
    Token(id=5, form='Česka', lemma='Česko', upos='PROPN', xpos='NNNS2-----A----', feats={'Case': 'Gen', 'Gender': 'Neut', 'NameType': 'Geo', 'Number': 'Sing'}, head=4, deprel='nmod', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=6, form='?', lemma='?', upos='PUNCT', xpos='Z:-------------', feats=None, head=4, deprel='punct', deps=None, misc={'SpaceAfter': 'No'}),
)

KLIC_SOUCAST_ZAMKU = (  # Klíč je součást zámku.
    Token(id=1, form='Klíč', lemma='klíč', upos='NOUN', xpos='NNIS1-----A----', feats={'Animacy': 'Inan', 'Case': 'Nom', 'Gender': 'Masc', 'Number': 'Sing'}, head=3, deprel='nsubj', deps=None, misc=None),
    Token(id=2, form='je', lemma='být', upos='AUX', xpos='VB-S---3P-AAI--', feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing', 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres', 'VerbForm': 'Fin', 'Voice': 'Act'}, head=3, deprel='cop', deps=None, misc=None),
    Token(id=3, form='součást', lemma='součást', upos='NOUN', xpos='NNFS1-----A----', feats={'Case': 'Nom', 'Gender': 'Fem', 'Number': 'Sing'}, head=0, deprel='root', deps=None, misc=None),
    Token(id=4, form='zámku', lemma='zámek', upos='NOUN', xpos='NNIS2-----A----', feats={'Animacy': 'Inan', 'Case': 'Gen', 'Gender': 'Masc', 'Number': 'Sing'}, head=3, deprel='nmod', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=5, form='.', lemma='.', upos='PUNCT', xpos='Z:-------------', feats=None, head=3, deprel='punct', deps=None, misc={'SpaceAfter': 'No'}),
)

KNIHA_MAJETEK = (  # Kniha je majetek knihovny.   (generalizace — unseen)
    Token(id=1, form='Kniha', lemma='kniha', upos='NOUN', xpos='NNFS1-----A----', feats={'Case': 'Nom', 'Gender': 'Fem', 'Number': 'Sing'}, head=3, deprel='nsubj', deps=None, misc=None),
    Token(id=2, form='je', lemma='být', upos='AUX', xpos='VB-S---3P-AAI--', feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing', 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres', 'VerbForm': 'Fin', 'Voice': 'Act'}, head=3, deprel='cop', deps=None, misc=None),
    Token(id=3, form='majetek', lemma='majetek', upos='NOUN', xpos='NNIS1-----A----', feats={'Animacy': 'Inan', 'Case': 'Nom', 'Gender': 'Masc', 'Number': 'Sing'}, head=0, deprel='root', deps=None, misc=None),
    Token(id=4, form='knihovny', lemma='knihovna', upos='NOUN', xpos='NNFS2-----A----', feats={'Case': 'Gen', 'Gender': 'Fem', 'Number': 'Sing'}, head=3, deprel='nmod', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=5, form='.', lemma='.', upos='PUNCT', xpos='Z:-------------', feats=None, head=3, deprel='punct', deps=None, misc={'SpaceAfter': 'No'}),
)

VLTAVA_REKA = (  # Vltava je řeka Česka.   (generalizace — unseen)
    Token(id=1, form='Vltava', lemma='Vltava', upos='PROPN', xpos='NNFS1-----A----', feats={'Case': 'Nom', 'Gender': 'Fem', 'NameType': 'Geo', 'Number': 'Sing'}, head=3, deprel='nsubj', deps=None, misc=None),
    Token(id=2, form='je', lemma='být', upos='AUX', xpos='VB-S---3P-AAI--', feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing', 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres', 'VerbForm': 'Fin', 'Voice': 'Act'}, head=3, deprel='cop', deps=None, misc=None),
    Token(id=3, form='řeka', lemma='řeka', upos='NOUN', xpos='NNFS1-----A----', feats={'Case': 'Nom', 'Gender': 'Fem', 'Number': 'Sing'}, head=0, deprel='root', deps=None, misc=None),
    Token(id=4, form='Česka', lemma='Česko', upos='PROPN', xpos='NNNS2-----A----', feats={'Case': 'Gen', 'Gender': 'Neut', 'NameType': 'Geo', 'Number': 'Sing'}, head=3, deprel='nmod', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=5, form='.', lemma='.', upos='PUNCT', xpos='Z:-------------', feats=None, head=3, deprel='punct', deps=None, misc={'SpaceAfter': 'No'}),
)

CO_JE_AUTO = (  # Co je auto?   (definiční otázka — mimo rozsah)
    Token(id=1, form='Co', lemma='co', upos='PRON', xpos='PQ--1----------', feats={'Animacy': 'Inan', 'Case': 'Nom', 'PronType': 'Int,Rel'}, head=3, deprel='nsubj', deps=None, misc=None),
    Token(id=2, form='je', lemma='být', upos='AUX', xpos='VB-S---3P-AAI--', feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing', 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres', 'VerbForm': 'Fin', 'Voice': 'Act'}, head=3, deprel='cop', deps=None, misc=None),
    Token(id=3, form='auto', lemma='auto', upos='NOUN', xpos='NNNS1-----A----', feats={'Case': 'Nom', 'Gender': 'Neut', 'Number': 'Sing'}, head=0, deprel='root', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=4, form='?', lemma='?', upos='PUNCT', xpos='Z:-------------', feats=None, head=3, deprel='punct', deps=None, misc={'SpaceAfter': 'No'}),
)

CITRON_OVOCE = (  # Citron je ovoce.
    Token(id=1, form='Citron', lemma='citron', upos='NOUN', xpos='NNIS1-----A----', feats={'Animacy': 'Inan', 'Case': 'Nom', 'Gender': 'Masc', 'Number': 'Sing'}, head=3, deprel='nsubj', deps=None, misc=None),
    Token(id=2, form='je', lemma='být', upos='AUX', xpos='VB-S---3P-AAI--', feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing', 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres', 'VerbForm': 'Fin', 'Voice': 'Act'}, head=3, deprel='cop', deps=None, misc=None),
    Token(id=3, form='ovoce', lemma='ovoce', upos='NOUN', xpos='NNNS1-----A----', feats={'Case': 'Nom', 'Gender': 'Neut', 'Number': 'Sing'}, head=0, deprel='root', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=4, form='.', lemma='.', upos='PUNCT', xpos='Z:-------------', feats=None, head=3, deprel='punct', deps=None, misc={'SpaceAfter': 'No'}),
)

OVOCE_OBSAHUJE = (  # Ovoce obsahuje vitamíny.
    Token(id=1, form='Ovoce', lemma='ovoce', upos='NOUN', xpos='NNNS1-----A----', feats={'Case': 'Nom', 'Gender': 'Neut', 'Number': 'Sing'}, head=2, deprel='nsubj', deps=None, misc=None),
    Token(id=2, form='obsahuje', lemma='obsahovat', upos='VERB', xpos='VB-S---3P-AAI--', feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing', 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres', 'VerbForm': 'Fin', 'Voice': 'Act'}, head=0, deprel='root', deps=None, misc=None),
    Token(id=3, form='vitamíny', lemma='vitamín', upos='NOUN', xpos='NNIP4-----A----', feats={'Animacy': 'Inan', 'Case': 'Acc', 'Gender': 'Masc', 'Number': 'Plur'}, head=2, deprel='obj', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=4, form='.', lemma='.', upos='PUNCT', xpos='Z:-------------', feats=None, head=2, deprel='punct', deps=None, misc={'SpaceAfter': 'No'}),
)

OBSAHUJE_CITRON = (  # Obsahuje citron vitamíny?  (rozbor bez podmětu: 2× obj)
    Token(id=1, form='Obsahuje', lemma='obsahovat', upos='VERB', xpos='VB-S---3P-AAI--', feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing', 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres', 'VerbForm': 'Fin', 'Voice': 'Act'}, head=0, deprel='root', deps=None, misc=None),
    Token(id=2, form='citron', lemma='citron', upos='NOUN', xpos='NNIS4-----A----', feats={'Animacy': 'Inan', 'Case': 'Acc', 'Gender': 'Masc', 'Number': 'Sing'}, head=1, deprel='obj', deps=None, misc=None),
    Token(id=3, form='vitamíny', lemma='vitamín', upos='NOUN', xpos='NNIP4-----A----', feats={'Animacy': 'Inan', 'Case': 'Acc', 'Gender': 'Masc', 'Number': 'Plur'}, head=1, deprel='obj', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=4, form='?', lemma='?', upos='PUNCT', xpos='Z:-------------', feats=None, head=1, deprel='punct', deps=None, misc={'SpaceAfter': 'No'}),
)

KAZDE_OVOCE = (  # Každé ovoce obsahuje vitamíny.
    Token(id=1, form='Každé', lemma='každý', upos='DET', xpos='PLNS1----------', feats={'Case': 'Nom', 'Gender': 'Neut', 'Number': 'Sing', 'PronType': 'Tot'}, head=2, deprel='det', deps=None, misc=None),
    Token(id=2, form='ovoce', lemma='ovoce', upos='NOUN', xpos='NNNS1-----A----', feats={'Case': 'Nom', 'Gender': 'Neut', 'Number': 'Sing'}, head=3, deprel='nsubj', deps=None, misc=None),
    Token(id=3, form='obsahuje', lemma='obsahovat', upos='VERB', xpos='VB-S---3P-AAI--', feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing', 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres', 'VerbForm': 'Fin', 'Voice': 'Act'}, head=0, deprel='root', deps=None, misc=None),
    Token(id=4, form='vitamíny', lemma='vitamín', upos='NOUN', xpos='NNIP4-----A----', feats={'Animacy': 'Inan', 'Case': 'Acc', 'Gender': 'Masc', 'Number': 'Plur'}, head=3, deprel='obj', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=5, form='.', lemma='.', upos='PUNCT', xpos='Z:-------------', feats=None, head=3, deprel='punct', deps=None, misc={'SpaceAfter': 'No'}),
)

PTACI_LETAJI = (  # Ptáci létají.   (generalizace — unseen)
    Token(id=1, form='Ptáci', lemma='pták', upos='NOUN', xpos='NNMP1-----A----', feats={'Animacy': 'Anim', 'Case': 'Nom', 'Gender': 'Masc', 'Number': 'Plur'}, head=2, deprel='nsubj', deps=None, misc=None),
    Token(id=2, form='létají', lemma='létat', upos='VERB', xpos='VB-P---3P-AAI--', feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Plur', 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres', 'VerbForm': 'Fin', 'Voice': 'Act'}, head=0, deprel='root', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=3, form='.', lemma='.', upos='PUNCT', xpos='Z:-------------', feats=None, head=2, deprel='punct', deps=None, misc={'SpaceAfter': 'No'}),
)

LETAJI_PTACI = (  # Létají ptáci?
    Token(id=1, form='Létají', lemma='létat', upos='VERB', xpos='VB-P---3P-AAI--', feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Plur', 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres', 'VerbForm': 'Fin', 'Voice': 'Act'}, head=0, deprel='root', deps=None, misc=None),
    Token(id=2, form='ptáci', lemma='pták', upos='NOUN', xpos='NNMP1-----A----', feats={'Animacy': 'Anim', 'Case': 'Nom', 'Gender': 'Masc', 'Number': 'Plur'}, head=1, deprel='nsubj', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=3, form='?', lemma='?', upos='PUNCT', xpos='Z:-------------', feats=None, head=1, deprel='punct', deps=None, misc={'SpaceAfter': 'No'}),
)

PROSTREDEK_URCEN = (  # Dopravní prostředek je určen k přepravě.
    Token(id=1, form='Dopravní', lemma='dopravní', upos='ADJ', xpos='AAIS1----1A----', feats={'Animacy': 'Inan', 'Case': 'Nom', 'Degree': 'Pos', 'Gender': 'Masc', 'Number': 'Sing', 'Polarity': 'Pos'}, head=2, deprel='amod', deps=None, misc=None),
    Token(id=2, form='prostředek', lemma='prostředek', upos='NOUN', xpos='NNIS1-----A----', feats={'Animacy': 'Inan', 'Case': 'Nom', 'Gender': 'Masc', 'Number': 'Sing'}, head=4, deprel='nsubj:pass', deps=None, misc=None),
    Token(id=3, form='je', lemma='být', upos='AUX', xpos='VB-S---3P-AAI--', feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing', 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres', 'VerbForm': 'Fin', 'Voice': 'Act'}, head=4, deprel='aux:pass', deps=None, misc=None),
    Token(id=4, form='určen', lemma='určený', upos='ADJ', xpos='VsYS----X-APP--', feats={'Aspect': 'Perf', 'Degree': 'Pos', 'Gender': 'Masc', 'Number': 'Sing', 'Polarity': 'Pos', 'Variant': 'Short', 'VerbForm': 'Part', 'Voice': 'Pass'}, head=0, deprel='root', deps=None, misc=None),
    Token(id=5, form='k', lemma='k', upos='ADP', xpos='RR--3----------', feats={'AdpType': 'Prep', 'Case': 'Dat'}, head=6, deprel='case', deps=None, misc=None),
    Token(id=6, form='přepravě', lemma='přeprava', upos='NOUN', xpos='NNFS3-----A----', feats={'Case': 'Dat', 'Gender': 'Fem', 'Number': 'Sing'}, head=4, deprel='obl', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=7, form='.', lemma='.', upos='PUNCT', xpos='Z:-------------', feats=None, head=4, deprel='punct', deps=None, misc={'SpaceAfter': 'No'}),
)

PROSTREDEK_URCEN_DLOUHY = (  # Dopravní prostředek je určen k přepravě nákladů a osob.
    Token(id=1, form='Dopravní', lemma='dopravní', upos='ADJ', xpos='AAIS1----1A----', feats={'Animacy': 'Inan', 'Case': 'Nom', 'Degree': 'Pos', 'Gender': 'Masc', 'Number': 'Sing', 'Polarity': 'Pos'}, head=2, deprel='amod', deps=None, misc=None),
    Token(id=2, form='prostředek', lemma='prostředek', upos='NOUN', xpos='NNIS1-----A----', feats={'Animacy': 'Inan', 'Case': 'Nom', 'Gender': 'Masc', 'Number': 'Sing'}, head=4, deprel='nsubj:pass', deps=None, misc=None),
    Token(id=3, form='je', lemma='být', upos='AUX', xpos='VB-S---3P-AAI--', feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing', 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres', 'VerbForm': 'Fin', 'Voice': 'Act'}, head=4, deprel='aux:pass', deps=None, misc=None),
    Token(id=4, form='určen', lemma='určený', upos='ADJ', xpos='VsYS----X-APP--', feats={'Aspect': 'Perf', 'Degree': 'Pos', 'Gender': 'Masc', 'Number': 'Sing', 'Polarity': 'Pos', 'Variant': 'Short', 'VerbForm': 'Part', 'Voice': 'Pass'}, head=0, deprel='root', deps=None, misc=None),
    Token(id=5, form='k', lemma='k', upos='ADP', xpos='RR--3----------', feats={'AdpType': 'Prep', 'Case': 'Dat'}, head=6, deprel='case', deps=None, misc=None),
    Token(id=6, form='přepravě', lemma='přeprava', upos='NOUN', xpos='NNFS3-----A----', feats={'Case': 'Dat', 'Gender': 'Fem', 'Number': 'Sing'}, head=4, deprel='obl', deps=None, misc=None),
    Token(id=7, form='nákladů', lemma='náklad', upos='NOUN', xpos='NNIP2-----A----', feats={'Animacy': 'Inan', 'Case': 'Gen', 'Gender': 'Masc', 'Number': 'Plur'}, head=6, deprel='nmod', deps=None, misc=None),
    Token(id=8, form='a', lemma='a', upos='CCONJ', xpos='J^-------------', feats=None, head=9, deprel='cc', deps=None, misc=None),
    Token(id=9, form='osob', lemma='osoba', upos='NOUN', xpos='NNFP2-----A----', feats={'Case': 'Gen', 'Gender': 'Fem', 'Number': 'Plur'}, head=7, deprel='conj', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=10, form='.', lemma='.', upos='PUNCT', xpos='Z:-------------', feats=None, head=4, deprel='punct', deps=None, misc={'SpaceAfter': 'No'}),
)

JE_AUTO_URCENO = (  # Je auto určeno k přepravě?
    Token(id=1, form='Je', lemma='být', upos='AUX', xpos='VB-S---3P-AAI--', feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing', 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres', 'VerbForm': 'Fin', 'Voice': 'Act'}, head=3, deprel='aux:pass', deps=None, misc=None),
    Token(id=2, form='auto', lemma='auto', upos='NOUN', xpos='NNNS1-----A----', feats={'Case': 'Nom', 'Gender': 'Neut', 'Number': 'Sing'}, head=3, deprel='nsubj:pass', deps=None, misc=None),
    Token(id=3, form='určeno', lemma='určený', upos='ADJ', xpos='VsNS----X-APP--', feats={'Aspect': 'Perf', 'Degree': 'Pos', 'Gender': 'Neut', 'Number': 'Sing', 'Polarity': 'Pos', 'Variant': 'Short', 'VerbForm': 'Part', 'Voice': 'Pass'}, head=0, deprel='root', deps=None, misc=None),
    Token(id=4, form='k', lemma='k', upos='ADP', xpos='RR--3----------', feats={'AdpType': 'Prep', 'Case': 'Dat'}, head=5, deprel='case', deps=None, misc=None),
    Token(id=5, form='přepravě', lemma='přeprava', upos='NOUN', xpos='NNFS3-----A----', feats={'Case': 'Dat', 'Gender': 'Fem', 'Number': 'Sing'}, head=3, deprel='obl', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=6, form='?', lemma='?', upos='PUNCT', xpos='Z:-------------', feats=None, head=3, deprel='punct', deps=None, misc={'SpaceAfter': 'No'}),
)

NUZ_VYROBEN = (  # Nůž je vyroben z oceli.   (generalizace — unseen)
    Token(id=1, form='Nůž', lemma='nůž', upos='NOUN', xpos='NNIS1-----A----', feats={'Animacy': 'Inan', 'Case': 'Nom', 'Gender': 'Masc', 'Number': 'Sing'}, head=3, deprel='nsubj:pass', deps=None, misc=None),
    Token(id=2, form='je', lemma='být', upos='AUX', xpos='VB-S---3P-AAI--', feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing', 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres', 'VerbForm': 'Fin', 'Voice': 'Act'}, head=3, deprel='aux:pass', deps=None, misc=None),
    Token(id=3, form='vyroben', lemma='vyrobený', upos='ADJ', xpos='VsYS----X-APP--', feats={'Aspect': 'Perf', 'Degree': 'Pos', 'Gender': 'Masc', 'Number': 'Sing', 'Polarity': 'Pos', 'Variant': 'Short', 'VerbForm': 'Part', 'Voice': 'Pass'}, head=0, deprel='root', deps=None, misc=None),
    Token(id=4, form='z', lemma='z', upos='ADP', xpos='RR--2----------', feats={'AdpType': 'Prep', 'Case': 'Gen'}, head=5, deprel='case', deps=None, misc=None),
    Token(id=5, form='oceli', lemma='ocel', upos='NOUN', xpos='NNFS2-----A---1', feats={'Case': 'Gen', 'Gender': 'Fem', 'Number': 'Sing'}, head=3, deprel='obl:arg', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=6, form='.', lemma='.', upos='PUNCT', xpos='Z:-------------', feats=None, head=3, deprel='punct', deps=None, misc={'SpaceAfter': 'No'}),
)

PROSTREDEK_SLOUZI = (  # Dopravní prostředek slouží k přepravě.
    Token(id=1, form='Dopravní', lemma='dopravní', upos='ADJ', xpos='AAIS1----1A----', feats={'Animacy': 'Inan', 'Case': 'Nom', 'Degree': 'Pos', 'Gender': 'Masc', 'Number': 'Sing', 'Polarity': 'Pos'}, head=2, deprel='amod', deps=None, misc=None),
    Token(id=2, form='prostředek', lemma='prostředek', upos='NOUN', xpos='NNIS1-----A----', feats={'Animacy': 'Inan', 'Case': 'Nom', 'Gender': 'Masc', 'Number': 'Sing'}, head=3, deprel='nsubj', deps=None, misc=None),
    Token(id=3, form='slouží', lemma='sloužit', upos='VERB', xpos='VB-S---3P-AAI--', feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing', 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres', 'VerbForm': 'Fin', 'Voice': 'Act'}, head=0, deprel='root', deps=None, misc=None),
    Token(id=4, form='k', lemma='k', upos='ADP', xpos='RR--3----------', feats={'AdpType': 'Prep', 'Case': 'Dat'}, head=5, deprel='case', deps=None, misc=None),
    Token(id=5, form='přepravě', lemma='přeprava', upos='NOUN', xpos='NNFS3-----A----', feats={'Case': 'Dat', 'Gender': 'Fem', 'Number': 'Sing'}, head=3, deprel='obl', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=6, form='.', lemma='.', upos='PUNCT', xpos='Z:-------------', feats=None, head=3, deprel='punct', deps=None, misc={'SpaceAfter': 'No'}),
)

JE_PETR_ZKUSENY = (  # Je Petr zkušený programátor?
    Token(id=1, form='Je', lemma='být', upos='AUX', xpos='VB-S---3P-AAI--', feats={'Aspect': 'Imp', 'Mood': 'Ind', 'Number': 'Sing', 'Person': '3', 'Polarity': 'Pos', 'Tense': 'Pres', 'VerbForm': 'Fin', 'Voice': 'Act'}, head=4, deprel='cop', deps=None, misc=None),
    Token(id=2, form='Petr', lemma='Petr', upos='PROPN', xpos='NNMS1-----A----', feats={'Animacy': 'Anim', 'Case': 'Nom', 'Gender': 'Masc', 'NameType': 'Giv', 'Number': 'Sing'}, head=4, deprel='nsubj', deps=None, misc=None),
    Token(id=3, form='zkušený', lemma='zkušený', upos='ADJ', xpos='AAMS1----1A----', feats={'Animacy': 'Anim', 'Case': 'Nom', 'Degree': 'Pos', 'Gender': 'Masc', 'Number': 'Sing', 'Polarity': 'Pos'}, head=4, deprel='amod', deps=None, misc=None),
    Token(id=4, form='programátor', lemma='programátor', upos='NOUN', xpos='NNMS1-----A----', feats={'Animacy': 'Anim', 'Case': 'Nom', 'Gender': 'Masc', 'Number': 'Sing'}, head=0, deprel='root', deps=None, misc={'SpaceAfter': 'No'}),
    Token(id=5, form='?', lemma='?', upos='PUNCT', xpos='Z:-------------', feats=None, head=4, deprel='punct', deps=None, misc={'SpaceAfter': 'No'}),
)
