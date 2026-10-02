---
name: report-writing
description: Write the prose of an evidence-led research report so its reader knows why to care, what was found, and how sure it is. Use when drafting or reviewing a report's title, opening, section headings, result statements, limits, or methods appendix.
---

# Report writing

Own the words a reader sees in an evidence-led report. Write it like a good
finance or economics paper, or a good talk: motivation, the problem, the
mental model, the approach, the answer, and why the answer matters. Keep it
brief. The reader wants a reason to care before they spend attention.

Know the reader, open with why it matters, use the reader's words, and give
each number its meaning. Code structure belongs to
[report-authoring](../report-authoring/SKILL.md); display belongs to
[report-presentation](../report-presentation/SKILL.md).

## Name the reader

Choose the reader before the first sentence: a pricing manager, a researcher,
a risk owner, a reviewer. Write down what they already know and what they should do
or believe after reading. Assume they know the domain but not this study,
its files, or its tools.

## Shape the report like a paper

1. **Title** — the main finding as a statement.
2. **Opening paragraph** — the abstract, in three to six sentences: the
   business context and why it matters, the question, the answer with its
   headline numbers in plain meaning, and what it implies or which decision it
   informs. Include every finding that would change that decision, even one
   that weakens the headline.
3. **Mental model** — the few terms and the picture the evidence needs, such
   as one diagram of how a coupon order adds margin and gives away a discount.
4. **Findings** — one section per claim, in order of importance. Each heading
   is the claim as a sentence. Each section leads with that claim, then the
   number, then the chart or table, then what the evidence does not show.
5. **Limits** — the scope of the claims, after the findings.
6. **Methods and reproduction** — data, design, checks, pipeline diagrams,
   environment, and commands. Here file names and tool names are fine,
   because the reader acts on them.

## State each result so it means something

- Give the unit and the direction in the reader's terms: "a coupon order
  keeps $0.50 of margin", not "net uplift is 0.497".
- Size it against something the reader values: the discount given, a cost, a
  baseline, a threshold.
- Give the uncertainty and the sample in the same sentence or the next one.
- Say what the result implies. Then say what it does not show.

## Keep the producer out of the reader's view

These belong in the methods appendix, the README, the journal, or a notes file:

- the report's own form or status: "narrative report", "this rewrite",
  "frozen", "accepted", "candidate", "clean run";
- file paths, file ownership, and tool or library names;
- verification against an earlier run, receipts, and cache decisions;
- open owner questions and agent notes;
- machine records such as JSON, receipts, and raw dictionaries. Say what the
  record shows in a sentence or a small table, and name the file that holds
  the full record;
- sections about setup or wiring. A setup cell displays nothing and needs no
  prose.

Code is the exception. It stays in the report, folded by the reading profile,
so a reader can open a cell and check how a number was made. Do not remove it
with `echo: false`. Hide only output that means nothing to a reader, such as a
progress log, with `output: false`.

## Example

The study is hypothetical. It shows the shape, not a domain.


Before (every sentence is short and active, and the reader learns nothing):

```text
Coupon C7: segment associations and history-lag sensitivity

This narrative report preserves the frozen four-week study. It consumes the
immutable pipeline outputs in ignored data/. It does not rerun the queries.
config.json owns the design. evidence/metrics.parquet owns the accepted estimates.
```

After:

```text
A 10% coupon barely pays for itself, and first-time buyers carry the gain

When we send a 10% coupon, some customers buy more, but we also give the
discount to customers who would have bought anyway. We measured both effects
over four weeks in March, using 48,210 coupon orders held out from model
fitting. A typical coupon order adds $4.10 of margin and gives away $3.60 in
discount. That leaves $0.50 per order (95% interval $0.30 to $0.70), but only
when each order counts once: weighted by customer or by order value, the
average coupon earns nothing. Coupon orders from first-time buyers keep about
$2.20 more than orders from repeat buyers, and a separate holdout month agrees.
A model using these signals targets coupons 3% better, but it loses that edge
when its purchase history is one day old.
```

## Check before finishing

Read only the title and the opening as the named reader. They should be able to
say why it matters, what was found, and what it means for them. Then read each
section heading in order: the headings alone should tell the story. Rewrite any
sentence you would not say aloud to that reader.
