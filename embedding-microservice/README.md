
# TODO
Best-practice way to do this
1. Keep the original chunk embedding

Embed the full 100-word chunk

This preserves factual detail and nuance

This is your ground truth

Never remove this.

2. Add a summary embedding as a secondary signal

Create a short, neutral summary (1–2 sentences)

Embed the summary separately

Use it to capture high-level intent

This helps with short or vague queries.