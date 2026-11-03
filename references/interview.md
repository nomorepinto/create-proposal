# Interview

Ask one example section per message. Wait for the answer. Then ask the next section.

If the user already supplied that fact, confirm it in one line and move on. If the user asks to hear the rest together, send the remaining sections in one message, still one question per section.

## Message shape

Use this shape for every section:

```
Section: {name as it appears in the example}

In the example, this section {what it is for}. Excerpt: "{one or two lines from the example}".

This answer fills {template slot}.

{One question asking for the same kind of content for the new event.}
```

Rules for that message:

- The excerpt shows the pattern. It is not the answer, and its facts (dates, names, prices, rules) stay out of the new proposal unless the user explicitly says that section stays the same.
- Match the excerpt's specificity. A list section asks for the new list and names the kinds of entries the example used.
- If that kind of section may not fit the new event, ask whether to keep a section like it, replace it, or drop it.
- Name the template slot the answer will fill. When the example has more detail than the template, say the extra detail will be written into the template slot that can hold it.

## Worked example: Date

The example records a single calendar date. The template has a Date label and a value cell beside it. Only the value changes.

```
Section: Date

In the example, this section records when the event happens. Excerpt: "December 10, 2025".

This answer fills the Date value in the template. The Date label stays as it is.

What is the date of the new event?
```

## Worked example: Description

The example uses several paragraphs: what the event is, why it is more than a competition, the tradition it starts, and the community it builds. The template has one Description cell. Each paragraph the user gives becomes its own paragraph in that cell.

```
Section: Description

In the example, this section is several paragraphs covering what the event is, why it is more than a competition, the tradition it starts, and the community it builds. Excerpt: "The Maybe the Night: Acoustic Evenings celebrates Mapúa University's musical brilliance, unity, and unwavering school spirit."

This answer fills the Description cell in the template, one paragraph per paragraph you write.

What should the description say for the new event? Write one paragraph per beat.
```

## Title and file name

Ask the title the way any other section is asked. In the same message, ask for the file's short name. Show the example filename. The short name is the token after ` - `, not the long title. The example title is "Maybe the Night: Acoustic Evenings" and the example file is `[COO] PROPOSAL - BOTB.pdf`, so the short name is `BOTB`.

```
The finished file follows that filename. The example uses the short name BOTB, while the title inside the document is longer.

What short name should the file use? Give it in the same style as BOTB: short and uppercase.
```

A different example file is parsed the same way. Quote that file's name, and ask for a short name in the style of its event token.
