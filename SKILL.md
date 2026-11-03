---
name: create-proposal
description: >-
  Analyzes a proposal template and an example proposal, asks one question per
  example section, and fills a copy of the Word template. Use when the user
  wants a new event proposal, a proposal from a template and an example, or a
  Word proposal based on an example proposal.
compatibility: Requires Python 3. PDF examples require pypdf.
---

# Create a proposal

Fill a copy of a Word proposal template. Use an example proposal only to decide what to ask and how specific each answer should be.

The template supplies the document: order, headings, tables, labels, boilerplate, and the signature block. The example supplies the interview. Facts from the example stay out of the new file unless the user explicitly says a section stays the same.

## Locate the two files

1. Use the template and example paths the user gave.
2. Otherwise use the pair in this skill directory (the folder that contains this `SKILL.md`):
   - Template: `[COO 2627] BOTB EVENT PROPOSAL.docx`
   - Example: `[COO] PROPOSAL - BOTB.pdf`

The template must be a `.docx`. The example may be a `.docx` or a `.pdf`.

## Extract

Run both commands and read the JSON. Paths in that JSON are the only paths you may fill.

```bash
python scripts/extract_proposal.py "<template.docx>"
python scripts/extract_proposal.py "<example.pdf>"
```

`p:N` is a body paragraph. `t:N,r:R,c:C` is a table cell. Empty paragraphs are included so the indexes stay stable.

On the bundled template, confirm the extractor still reports this map before you fill. If a path differs, the extractor wins.

- Title: `p:0`
- Header table `t:0`, values in column `c:2`: date `r:0`, time `r:1`, main objective `r:2`, proponents `r:3`, participants `r:4`, description `r:5`
- Objectives: `p:5` through `p:7`. Leave `p:4` (`Objectives:`) as it is.
- Guidelines: `p:12` through `p:14`. Leave `p:11` (`GENERAL GUIDELINES`) and `p:15` (`BUDGET PROPOSAL`) as they are.
- Budget table `t:1`. Header is row `0`. Clone a category from row `1` (1 cell), an item from row `2` (4 cells), a subtotal from row `5` (2 cells), and the total from row `11` (2 cells).
- Program table `t:2`. Keep rows `0` and `1`. The day header is `t:2,r:0,c:0` (two paragraphs). Clone a segment from row `2` (3 cells: time, program, remarks).
- Signature lines: proponent name `p:59`, position `p:60`; noted-by names `p:66`, positions `p:67`; president `p:70`, position `p:71`; approver `p:77`, position `p:78`.

Leave these as written unless the user explicitly changes one: the field labels (`Date`, `Time`, `Main Objective`, `Project Proponent`, `Target Participants`, `Description`), column labels (`EXPENSES`, `UNIT COST`, `QUANTITY`, `TOTAL`, `TIME`, `PROGRAM`, `REMARKS`), the section headings, the motto (`p:56`), the approval-request sentence (`p:54`), `Noted by:` (`p:63`), and `Approved by:` (`p:74`).

## Interview

Split the example into sections in the example's own order. A section is a title, a labeled field, a heading, a subsection, or a table. For the bundled example that is the title, the objectives, each header field, the description, each guidelines subsection, the program flow, the budget, and the closing sign-off. A different example produces a different list. Derive the list from the extract. Do not reuse this list for another example.

Read [references/interview.md](references/interview.md) and follow that message shape for every section.

Ask one section, then wait. With the title, also ask for the file's short name, as that reference describes.

Where the example is richer than the template, ask at the example's specificity and write the answer into the template slot:

- Guideline subsections are written as paragraphs in the guidelines range. Each subsection the user keeps becomes its own paragraphs. A dropped subsection is omitted.
- Program flow is written in the template columns Time, Program, and Remarks. Ask for those. The example also records duration and a longer description; ask the user to put that detail in remarks.
- Budget lines use the template columns: category, item, unit cost, quantity, and total, plus a subtotal per category and a final total. Write amounts as `PHP 1,250.00` (peso sign is not used in this template).
- Objectives are written `Name – what it achieves`. The dash keeps the template's bold lead and regular explanation.
- The signature block follows the template's roles. Ask who the proponent, the noted-by officers, and the approver are. The example's approver is a fact about that example, not the default for the new file.

## Write the file

Build a JSON file in a temporary directory (do not leave it in the skill folder) and run the filler. The filler copies the template and edits that copy. It is the only way to produce the Word file.

```bash
python scripts/fill_proposal.py --template "<template.docx>" --answers "<answers.json>" --example "<example file>" --short-name "<SHORT>" --out-dir "<current project>"
```

`--out-dir` is the current project, the folder where the new proposal is being written. Give the filled `.docx` path to the user.

### Output name

The filename follows the example file, not the template file.

`[COO] PROPOSAL - BOTB.pdf` plus the short name `ACOUS` becomes `[COO] PROPOSAL - ACOUS.docx`.

The script keeps the example's prefix, word, separator, and capitalization, replaces the token after ` - `, and uses `.docx`. If that file already exists, it inserts ` 2`, ` 3`, and so on before the extension. It will not overwrite the template or the example.

### Answers file

```json
{
  "set_text": [
    {"path": "p:0", "text": "Event title"},
    {"path": "t:0,r:0,c:2", "text": "January 15, 2027"},
    {"path": "t:0,r:3,c:2", "paragraphs": ["Name of Officer", "Position, Mapúa COO", "name@mymail.mapua.edu.ph"]},
    {"path": "t:0,r:5,c:2", "paragraphs": ["First description paragraph.", "Second description paragraph."]},
    {"path": "t:2,r:0,c:0", "paragraphs": ["Day 1", "January 15, 2027 | 10:00 AM - 3:00 PM | Venue"]}
  ],
  "replace_paragraphs": [
    {"start": "p:5", "end": "p:7", "texts": ["Bring people together – What this event does."]},
    {"start": "p:12", "end": "p:14", "texts": ["Eligibility:", "Who may join.", "Song choice", "How songs are chosen."]}
  ],
  "rebuild_rows": [
    {
      "table": "t:1",
      "keep_rows": [0],
      "rows": [
        {"clone_row": 1, "cells": ["Production"]},
        {"clone_row": 2, "cells": ["LED wall", "PHP 20,000.00", "1", "PHP 20,000.00"]},
        {"clone_row": 5, "cells": ["SUBTOTAL", "PHP 20,000.00"]},
        {"clone_row": 11, "cells": ["TOTAL AMOUNT", "PHP 20,000.00"]}
      ]
    },
    {
      "table": "t:2",
      "keep_rows": [0, 1],
      "rows": [
        {"clone_row": 2, "cells": ["10:00 AM - 10:15 AM", "Opening", "15 minutes"]}
      ]
    }
  ]
}
```

`set_text.text` is one paragraph (`\n` is a line break inside it). `set_text.paragraphs` is one paragraph per entry. Use `paragraphs` for the proponent cell, the description, and the program day header. In the proponent cell, give each person as name, position, then email. Put a blank string between people. The template already styles the paragraphs in that order.

`replace_paragraphs` replaces every paragraph from `start` through `end`, including empty paragraphs between them. The new paragraphs are clones of the first paragraph in that range, so numbering and fonts stay. An empty `texts` list removes that range. Keep ranges from crossing a heading or a table you need to preserve. Apply the objectives range and the guidelines range on the bundled template.

`rebuild_rows` keeps the listed rows (the header, in its original place), removes every other row in that table, and appends `rows`. Each appended row is a clone of `clone_row` from the template, and `cells` must have one entry per cell in that cloned row. A cell entry is a string, or a list of strings when that cell needs several paragraphs. Put category, item, subtotal, and total rows in the order they should appear, including the total as the last row.

Cell counts on the bundled template: category `1`, item `4`, subtotal `2`, total `2`, program segment `3`.

If a path is not in the template, the filler writes no file and reports that path.

## Finish

Tell the user the filled `.docx` path. Mention any section they chose to drop. Leave the template file and the example file unchanged.
