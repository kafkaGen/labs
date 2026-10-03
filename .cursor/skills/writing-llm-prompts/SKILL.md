---
name: writing-llm-prompts
description: Use when writing, rewriting, or reviewing a prompt for an LLM that will be saved or reused, such as a system prompt, a prompt template with variables, an agent or bot prompt, or a prompt the user will paste into a chat model.
---

# Writing LLM prompts

## Overview

A good prompt tells the model exactly what job to do and gives it everything it needs for that job, and nothing more. Every prompt in this repo follows the same standard: plain, direct language, content split into XML-tagged blocks, and runtime values at the end.

Work in four steps. Check that the job is doable, split the prompt into blocks, write each instruction clearly, then test it.

## Step 1: check the job before you write

Models are good at judgment. They understand messy requests, decide what matters, write, explain, and handle cases nobody listed. They are unreliable at mechanical work: counting, arithmetic, sorting, parsing or validating data, date math, unit conversion, and anything that needs current or private data. Each mechanical step left in a prompt is a place where the model can be wrong without anyone noticing.

Go through the request step by step. For each step, ask whether code could do it exactly. If it could, move that step out of the prompt and give the model the result instead.

| Mechanical step | Where it goes |
|---|---|
| Counts, totals, percentages, sorting | A script runs first and passes the numbers in. |
| Fixed business rules, such as "enterprise tickets get one priority level higher" | Code applies them after the model answers. |
| Choosing one label from a fixed list | Structured outputs or a tool with an enum, so an invalid label can't happen. |
| JSON output | Structured outputs when the API supports them, otherwise validation in code. |
| Current versions, prices, news, private systems | A tool, or data the human pastes in. Without one, the model invents it. |

Then warn the human about anything still missing. Put the warning above the prompt, never inside it. Raise a warning when:

- the job needs data or actions the model has no tool for,
- a mechanical step still has no tool or script, or
- the request is too vague to write rules for, because it has no audience, no output shape, or no way to tell a good result from a bad one.

Each warning says what is missing, what goes wrong without it (invented data, wrong counts, an unpredictable format), and which tool or input would fix it. Then write the best prompt the current setup allows, unless the human needs to answer a question first.

## Step 2: split the prompt into tagged blocks

Put each kind of content in its own XML block. The tags show the model where instructions end and data begins. They also let one block point at another without ambiguity, as in "use the plan tier from `<context>`".

These four core blocks belong in almost every prompt:

| Block | What goes in it |
|---|---|
| `<role>` | One or two sentences: who the model is and what its task is. This is the first thing the model reads. |
| `<instructions>` | What to do. Use numbered steps only when the order matters. |
| `<rules>` | Hard limits. Each rule is something the output either obeys or breaks. |
| `<quality_criteria>` | What a good result looks like. The model checks its output against these before answering. |

Add these blocks when the case needs them:

| Block | When to add it |
|---|---|
| `<context>` | The prompt has runtime values. |
| `<output_format>` | The output has a fixed shape: fields, order, types, or a defined empty result. |
| `<examples>` | The format or the judgment is easier to show than to describe. See Step 4. |

These lists are a starting point, not a limit. Create whatever other blocks the case calls for, such as `<tools>`, `<voice>`, `<categories>`, `<background>`, or `<documents>`. Leave out any block that would be empty or would only state the obvious. Name tags in `snake_case` after their content. When content fits one of the blocks above, use that tag name, so the same content has the same tag in every prompt.

### Static content first, changing content last

Providers cache a prompt from its first token up to the first token that differs between calls. So put every static block first and every runtime value at the end. A single `{{user_name}}` inside `<role>` makes the whole prompt uncacheable. In static blocks, refer to a value by its tag, as in "the plan tier in `<context>`", not by the variable itself.

Name variables `{{snake_case}}` and wrap each one in a tag with the same name.

Place long input, such as a document, a diff, or a transcript, by whether it changes between calls, not by its length. A handbook that is the same on every call is static: put it after the other static blocks and before `<context>`, so it gets cached too. A diff or a ticket that changes every call goes after `<context>`. Either way, put the specific request last. Anthropic's tests show answers improve when the question comes after a long document.

```xml
<context>
<plan_tier>{{plan_tier}}</plan_tier>
<account_age_days>{{account_age_days}}</account_age_days>
</context>

<ticket>
{{ticket_text}}
</ticket>

Triage the ticket above.
```

## Step 3: write each instruction

Use this test: a smart new colleague with no background on the project reads the prompt. Could they do the job without asking you anything? If they would be confused, the model will be too.

- **State the task first, in plain words.** The opening line of `<role>` says what the job is: "You triage support tickets for a SaaS product." One sentence of role is enough. A heavy persona, such as "a world-class expert who never makes mistakes", narrows the model without helping it.
- **Give instructions, not questions, and lead with action verbs:** write, list, classify, change. The verb decides what the model does. "Suggest changes" gets suggestions back, and "change the function" gets edits.
- **Be specific.** Use numbers, names, and limits. Write "at most three sentences", not "be concise".
- **Say what to do, not only what to avoid.** "Write in plain paragraphs" works better than "don't use markdown".
- **Give the reason when a rule isn't self-explanatory.** The model generalizes from reasons. "The reply is read aloud by text-to-speech, so write numbers as words" also covers cases that the bare rule would miss.
- **Use calm wording.** Current models follow instructions closely, and words like CRITICAL, MUST, or ALWAYS in capitals make them over-apply a rule. Write "Use this tool when...".
- **Use the same word for the same thing in every block.** If `<instructions>` says "ticket", don't call it "request" or "issue" in `<rules>`. If priorities are "P1 to P4", don't call P1 "urgent" elsewhere. The model may read a new word as a different thing and guess what it means.
- **Describe how things work now.** Leave out history. "Do not comment on style" is a rule. "We no longer want style comments" is history.
- **Write the prompt in the style you want back.** A prompt full of markdown bullets gets markdown bullets back.
- **Cut every word that doesn't change behavior:** politeness, hedges, filler, and explanations of things the model already knows. Keep each sentence complete and natural to read. The goal is clarity, not the shortest possible text.

| Instead of | Write |
|---|---|
| Please try to find bugs if there are any, and let us know what you think. | Report every defect in the diff that changes runtime behavior. |
| Be concise. | Answer in at most three sentences. |
| NEVER use ellipses! | The reply is read aloud by a speech engine, which can't pronounce ellipses, so don't use them. |
| Could you make sure the answer says where it applies? | Name the location and the date range in every answer. |

### Aim between vague and hardcoded

Prompts fail in two opposite directions. Vague guidance assumes context the model doesn't have. Hardcoded if-else logic breaks on the first case nobody listed. Aim between the two: state the goal clearly, add the heuristics that matter, and let the model reason. For a reasoning task, "think it through before answering" usually beats a step-by-step plan written by hand. Don't try to list every edge case. A few well-chosen examples cover more ground.

### Keep answers grounded

- **Allow "I don't know".** Write something like "If the data doesn't show it, say so", or "Use null for any field the text doesn't state". This cuts down on invented answers.
- **Limit the sources when you need to.** If answers must come only from the material provided, say so. For long documents, ask the model to quote the relevant passages first and answer from those quotes.
- **Ask for a self-check against `<quality_criteria>`** before the model gives its final answer.

## Step 4: add examples only where they help

Add examples when the output format is easier to show than to describe, or when the right answer depends on judgment that rules can't pin down. Skip them for simple answers that a single rule already makes clear.

- Start with one example. Add a second or third only when outputs copy the first example's surface details or miss a kind of input.
- Models copy details from examples closely. Make each example realistic, and make them differ from one another in length, input type, and edge cases.
- Wrap each one in `<example>` inside `<examples>`. Use real values, never placeholders or variables.

## Step 5: test the prompt

Run the prompt on three to five realistic inputs, including at least one hard case. Check each output against `<quality_criteria>`, and check that the runs agree with each other. If you can't run the model yourself, give the human those test inputs and tell them what to look for.

Fix what actually failed. Add an instruction or an example for the failure you saw, not for failures you imagine. If one prompt keeps doing several jobs badly, split it into a chain of separate calls, such as draft, then review, then revise. Each call then does one job and can be checked on its own.

## Common mistakes

| Mistake | Fix |
|---|---|
| The prompt reads well, but the job is impossible with the tools available | Warn the human above the prompt, and name the missing tool or input. |
| The model counts, sorts, computes, or applies fixed rules | Move that work into code, and pass the result in. |
| A variable sits in `<role>`, in a step, or in an example | Move it into `<context>`, and refer to it by tag. |
| Markdown headings instead of XML blocks | Use tagged blocks. Markdown lists inside a block are fine. |
| Every block from the list appears, even when empty | Keep only the blocks this case needs. |
| A long list of edge-case rules | Replace it with clear heuristics and one or two examples. |
| A rule explains its own history | Keep the rule, and drop the story. |
| Capitals and threats ("you MUST", "CRITICAL") | State the rule calmly, and give its reason. |
