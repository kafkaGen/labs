# Vision: weather-agents

**Status:** Active

**In one line:** A weather chat CLI built as a study rig for the Anthropic stack: an advanced MCP server over Open-Meteo, driven by a delegating multi-agent system that is implemented twice, once on the Claude API and once on the Claude Agent SDK.

## Problem

I have real practice with the Anthropic stack, but all of it ad hoc: I learn what the task in front of me needs and stop there. So I know a few features well and the rest of the toolset only by name, including MCP transports beyond stdio, sampling, elicitation, notifications, and agents that delegate to other agents. Now I want the whole scope Anthropic offers, nuances included, and to try each part by hand rather than only read about it.

## Goal

One system, grown in passes, that I have built by hand from the protocol up: a weather CLI whose orchestrator delegates to specialist agents over an MCP server I wrote, with the agent layer implemented twice on identical tools and prompts. Once it works, I can build agents, multi-agent systems, and MCP servers on the Anthropic stack without reaching for a tutorial.

## Learning objectives

Learn the Anthropic stack deeply enough to build with it unaided. The syllabus is Anthropic's own material: the MCP and Advanced MCP courses, Claude Code in Action, and the Claude API and Agent SDK documentation. Each course leaves working code in this package rather than notes. An area counts as learned when the code runs and I can explain it from memory. Where the fast way to ship and the way that teaches me more disagree, the slower one wins: this project exists to be built, not to be finished.

## Users

Me, and nobody else. No one else runs it, reads it, or depends on it.

## Core use cases

- I start the CLI, pick the agent runtime for the session (Claude API or Claude Agent SDK), and hold a free-text conversation about weather.
- I ask a compound question, like whether this weekend suits a hike near a given town, and the orchestrator works out the steps, delegates them to specialist agents, and merges what comes back into one answer.
- I clear the conversation and start a fresh one without leaving the CLI.
- I add another advanced MCP capability to the server and exercise it through a conversation, so the feature is visible from the outside rather than only present in the code.

## In scope

- An MCP server over Open-Meteo exposing all three primitives: tools, resources with templates, and prompts.
- Both stdio and streamable HTTP transports on that server, kept working side by side rather than one replacing the other.
- The advanced protocol surface, added a piece at a time across passes: sampling, elicitation, progress notifications, structured logging, and authorization on the HTTP transport.
- An orchestrator agent that decides which specialist handles what, and chains steps itself when a task needs more than one.
- Two interchangeable agent runtimes behind the same tools and the same prompts, selected when the CLI starts.
- Conversation state held in memory for the life of a session.
- Open-Meteo's numbers taken as given. What this adds is retrieval, reasoning, and presentation.

## Out of scope

- Conversations that survive the process, and any memory across sessions. Comes back when losing context between runs actually costs me something.
- Any interface beyond the CLI. Comes back when a multi-agent run gets unreadable in a terminal.
- Data domains other than weather. Comes back only if Open-Meteo runs out of interesting shapes, which its endpoint list suggests will take a while.

## Non-goals

- Anything other people use. No deployment, no uptime, no support. This is the line that keeps hardening work from displacing learning work.
- Other model providers. The project is about one stack, and a provider abstraction would hide exactly the layer I am here to learn.
- Agent frameworks such as LangChain, LangGraph, or CrewAI. They solve the problems I want to solve myself.
- Benchmarking models and parameters against each other for their pros and cons. It was in the original idea and it is out: measuring models is not the skill I am after, and picking a model per agent is a configuration detail rather than an experiment.

## Success criteria

- The same conversation runs correctly through both runtimes, chosen at startup, with no change to the tools or the prompts behind them.
- Every advanced MCP capability listed in scope has a CLI flow that visibly exercises it. An implementation with nothing driving it does not count.
- I can explain any part of the system from memory, without rereading the code.

## Constraints

- Evenings and weekends, a few hours a week, with no deadline. Anything that only pays off over a long uninterrupted stretch will not get built.
- API spend capped at roughly $10 to $20 a month, so cheap models are the default and the expensive ones get used deliberately.
- Python 3.12 inside the `labs` uv workspace, with the repo's ruff and ty configuration.
- Open-Meteo's free tier: no API key, CC-BY attribution, non-commercial use, and published rate limits. Assumed: those limits are comfortable for one person at a CLI, and nothing here needs a paid plan.
