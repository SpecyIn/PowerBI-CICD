# Power BI PBIP Conflict & Format Resolver - Beginner's Wiki Guide
> **Simple User Manual for [`PBIP-ConflictsResolve.py`](file:///c:/Users/shiva/Documents/Projects/USDT-Manager/PBIP-ConflictsResolve.py)**  
> *Designed for developers and team members new to Git and Power BI merge conflicts.*

---

## 🌟 What is this tool and why do I need it?

When multiple people work on the same Power BI report (`.pbip` / `.tmdl` / `.json`), Git sometimes gets confused about whose changes to keep. When this happens, Git inserts **merge conflict markers** into your files that look like this:

```text
<<<<<<< HEAD
    lineageTag: 12345-abcde   (Your current code)
=======
    lineageTag: 67890-fghij   (Incoming code from your teammate)
>>>>>>> feature/branch
```

If you leave these markers inside your files, Power BI Desktop will fail to open the report! 

**This tool automatically fixes these merge conflicts, removes duplicate items, fixes missing JSON commas, and cleans up your files so your Power BI report opens smoothly every time!**

---

## 🚀 Quick Start (3 Easy Steps)

### Step 1: Open Command Prompt or Terminal
Open your terminal inside your project folder.

### Step 2: Run the Tool
Type this command and press **Enter**:

```bash
python PBIP-ConflictsResolve.py
```

*(Or drag and drop your report folder path into the command: `python PBIP-ConflictsResolve.py "C:\Path\To\MyReport"`)*

### Step 3: Pick an Option from the Menu
The tool will show you a menu with 5 modes. Just type the number you want and press **Enter**!

---

## 🎛️ Main Menu Explained (In Plain English)

| Menu Option | What it does | When should I use it? |
| :--- | :--- | :--- |
| **`1` - Resolve Git Conflict Markers** | Finds and fixes all Git conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`). | **Use when Git merge fails** or when you see conflict markers in your files. |
| **`2` - Resolve Duplicate Objects & Auto-Format** | Removes duplicate columns/measures and auto-fixes missing JSON commas & Field Parameters. | **Use after merging code** to ensure JSON files and Field Parameters are clean. |
| **`3` - Stage Clean Files to Git** | Automatically runs `git add` on all clean, fixed files so you can commit them. | **Use after resolving conflicts** to stage your fixed files in 1 second. |
| **`4` - Metadata Health Check** | Scans your whole report to check for hidden errors or remaining conflict markers. | **Use before pushing your code** to verify your report is 100% healthy. |
| **`5` - Detailed Conflict Review** | Shows you a line-by-line comparison of changes before you choose what to keep. | **Use when you want to carefully inspect differences** line by line. |

---

## ⌨️ Cheat Sheet: What key do I press during conflict review?

When the tool shows you a conflict, Option **`[1]`** is ALWAYS the **Incoming Change** (your teammate's work on top), and Option **`[2]`** is ALWAYS the **Current Branch** (your work on bottom).

| Press | What it means | Example |
| :---: | :--- | :--- |
| **`1`** | **Keep Option 1 (Incoming Change)** | Keeps your teammate's incoming change. |
| **`2`** | **Keep Option 2 (Current Branch)** | Keeps your own local change. |
| **`1A`** | **Accept Option 1 for ALL items in this category** | Auto-keeps Option 1 for all remaining items in this section so you don't have to keep pressing `1`. |
| **`2A`** | **Accept Option 2 for ALL items in this category** | Auto-keeps Option 2 for all remaining items in this section. |
| **`s`** | **Skip** | Skips this conflict for now and leaves it untouched. |
| **`b`** | **Back to Main Menu** | Returns to the Main Menu if you made a mistake or want to choose another option. |

> 💡 **Tip**: If you type `1A` or `2A`, it only applies to that specific property section (e.g. LineageTags). When the script moves to Bookmarks or Additions, it will safely ask you again!

---

## 📖 Practical Examples (How do I fix my task?)

### Example A: "I got a Git merge conflict after pulling code!"
1. Run `python PBIP-ConflictsResolve.py`.
2. Type `1` for **Resolve Git Conflict Markers**.
3. Type `6` for **All Conflict Markers (Combo Mode)**.
4. The tool will guide you through each conflict. Type `1` or `2` (or `1A` / `2A` to speed up).
5. When finished, select **Option 3 (Stage Clean Files)** to stage all fixed files.
6. Commit your changes in Git (`git commit -m "Resolved conflicts"`). You're done!

---

### Example B: "Someone added new columns to a Field Parameter and JSON formatting broke!"
1. Run `python PBIP-ConflictsResolve.py`.
2. Type `2` for **Resolve Duplicate Objects & Auto-Format**.
3. Type `4` for **JSON Comma & Field Parameter Auto-Formatter**.
4. The script will automatically fix missing commas (`},\n{`), remove duplicate commas, and adjust Field Parameter item lengths & indices!

---

### Example C: "I want to make sure my report has zero errors before I push!"
1. Run `python PBIP-ConflictsResolve.py`.
2. Type `4` for **Health Check**.
3. The tool will print a green `[OK] HEALTH CHECK PASSED!` if everything is clean, or list any remaining issues with line numbers.

---

## ❓ Frequently Asked Questions (FAQ)

#### Q: Will this tool break my Power BI report?
**No.** The script is built specifically for Power BI PBIP and Fabric files. It respects UTF-8 file encoding, automatically fixes JSON syntax errors, and cleans up blank lines.

#### Q: What if I select the wrong option during review?
You can type **`s`** to skip an item, or type **`b`** at any sub-menu prompt to go back to the Main Menu without breaking anything.

#### Q: Why is Option 3 (Staging) so fast?
Mode 3 checks your Git status directly at the repository root in ~10 milliseconds. It skips files that are already clean or staged, saving you time.

---

*Happy reporting! If you have any questions, reach out to your team lead.*
