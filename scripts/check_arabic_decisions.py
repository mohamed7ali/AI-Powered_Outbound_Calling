from outbound_ai.telephony.routing import decide_follow_up

samples = [
    "نعم، المشكلة حُلّت",
    "تم حل المشكلة، المشكلة اتحلت، اه",
    "تم حل المشكله المشكله اتحلت ايوه",
    "المشكلة اتحلت نعم",
    "نعم تم حل المشكلة",
    "المشكلة اتحلت",
    "أجل، تم حلها",
    "بلى، انتهت المشكلة",
    "لا، المشكلة لم تُحل",
    "المشكلة ما زالت موجودة",
    "لا تزال المشكلة قائمة",
    "لم تنته المشكلة",
    "لا أعرف",
    "الكلام غير واضح",
]

for sample in samples:
    decision = decide_follow_up(speech=sample)
    print(f"{sample}\t{decision.action}\t{decision.reason}")
