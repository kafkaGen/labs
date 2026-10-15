# Misconception: appending a user turn invalidates the messages cache

In lesson 4's prediction quiz, the user answered "From messages" for appending a new user turn to an unchanged conversation. The right answer is a full hit. They seem to read "the messages array changed" as "the messages cache breaks", instead of asking whether any token that was already in the prefix changed. This matters because appending a turn is the most common request in any conversation. Getting it wrong overestimates the cost of every multi-turn agent, and blurs the difference between appending and editing that the routing advice depends on.

**Evidence**: lesson 4, prediction 1, reported in chat on 12 October 2026. The explanation was given in chat. The user has not yet shown they now understand it.

**Implications**: the lab's step 1 row (read is about 100%, fresh is only the new turn) is the direct counter-evidence, so point at it when the user pastes output. Retest in the next warm-up with a variant: append a tool result, or append an assistant turn. If the user gets it right, mark this record superseded.
