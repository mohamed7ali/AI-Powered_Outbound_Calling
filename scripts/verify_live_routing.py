import inspect

from outbound_ai.telephony.routing import FollowUpAction, decide_follow_up

speech = "تم حل المشكلة، المشكلة اتحلت، اه"
decision = decide_follow_up(speech=speech)

print("routing_file=", inspect.getsourcefile(decide_follow_up))
print("speech=", speech)
print("action=", decision.action)
print("reason=", decision.reason)

if decision.action != FollowUpAction.RESOLVED:
    raise SystemExit("FAIL: the imported routing.py does not classify the affirmative answer as RESOLVED")

print("PASS: affirmative Arabic answer is classified as RESOLVED")
