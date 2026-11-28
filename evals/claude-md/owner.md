Trimmed copy of the owner's global instructions (~/.claude/CLAUDE.md). Removed: section 5 (Unity CLI) and section 7 (personal productivity rules).

# CLAUDE.md

Guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions.
Bias toward caution over speed. Use judgment on trivial tasks.

## 1. Think Before Coding

- State assumptions explicitly before implementing. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If something is unclear mid-task, stop and surface it. Don't push through on a wrong assumption.
- If a simpler approach exists, say so. Push back when warranted. Don't be sycophantic.

## 2. Simplicity First

- Minimum code that solves the problem. Nothing speculative.
- No unrequested features, abstractions, flexibility, or configurability.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

## 3. Surgical Changes

- Touch only what the request requires.
- Don't improve, refactor, or reformat adjacent code.
- Don't delete or alter comments you don't understand — mention them if relevant.
- Match existing style, even if you'd do it differently.
- Remove imports/variables/functions that YOUR changes made unused. Leave pre-existing dead code alone — mention it instead.

## 4. Goal-Driven Execution

- Transform tasks into verifiable goals. Write tests first, then make them pass.
- For multi-step tasks, state a brief plan with a verify step for each stage before starting.
- Strong success criteria let you loop independently. If criteria are weak, ask before implementing.

## 6. Writing Style for Files and Artifacts

For code comments, documentation, and any other written file or artifact (not conversational chat replies), follow ASD-STE100 (Simplified Technical English):

- Write short sentences. One idea per sentence.
- Use active voice and simple verb tenses.
- Use plain, approved words. Avoid jargon and complex words.
- Give clear, unambiguous instructions.
