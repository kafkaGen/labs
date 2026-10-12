# Notes

- The user asked three questions at the start: what the best practices for routing are, where routing is most efficiently implemented, and how to keep prompt caching working in a conversation that has routing. Every lesson should advance at least one of them.
- Scope picked by the user: intent routing and model routing. Mixture-of-experts routing is out.
- The user has a related project, `packages/weather-agents` (an orchestrator delegating to specialist agents on the Claude API). Use it for examples, but the mission is general, so don't make lessons depend on it.
- Writing style: follow `.cursor/rules/agent-voice.mdc`. Plain words, no em dashes, sentence-case headings.

## Planned sequence (revise freely)

1. The cache key and how each routing move hits it. (lesson 0001)
2. Where routing lives: application vs gateway vs server, and stickiness at each layer. (lesson 0002)
3. Router best practices: route-before vs cascade, classifier design, threshold, random-router baseline, edge-case evals. (lesson 0003)
4. Hands-on: predict, then run `assets/cache_lab.py` and read `usage` fields. (lesson 0004) Runs on Sonnet 5.5, not Haiku: Haiku 4.5's 4,096-token minimum would force a bigger, costlier prompt, and Haiku 5.5 is missing from the caching docs' minimum-length list.
5. Undecided. Pick from the lesson 4 output and scores: a review of whatever mismatched, or a design exercise applying all four lessons to one agent.

## Session log for ZPD

- Lesson 0001: the user said "done" a week later but gave no score. No learning record yet. Lesson 0002 opens with three lesson-1 retrieval items, partly to get that evidence.
- Lesson 0002: the user said "next lesson" two days later, again with no score. Still no learning record.
- Lesson 0003: "next lesson" 23 minutes later, no score. Lessons are going faster than spacing would like.
- Lesson 0004 asks the user to paste the lab output and scores. The script's first real run hasn't happened yet: if it errors (role=system message format, max_tokens=0 on some model), fix the script first.
- 12 Oct: scores reported. Lesson 2 was 7 of 9 (missed W2 tool-description edit, W3 image). Lesson 3 was 9 of 10 (missed Q7, skip the router). See learning record 0002. The user didn't know scores had to be typed into chat. Each lesson now asks for this explicitly.
- 12 Oct: lesson 4 predictions were 7 of 8. The miss was prediction 1 (picked "From messages" for an appended user turn). See learning record 0003. Lab not run yet.
- Lesson 5 warm-up must include: an appended turn or tool result (record 0003), a tool-description edit, an image (record 0002), and "do you need a router at all?" (record 0002).
- Each lesson should open with a short retrieval warm-up on the previous lesson (spacing). Lesson 0003 interleaves items from lessons 1 and 2.
