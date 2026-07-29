# מסמך יכולות — עוזר RTM (Milestone B)

מסמך קצר למה שהעוזר **יודע לעשות עכשיו**, עם דוגמאות פרומפטים.
לא תכנון עתידי — רק מה שעובד בפועל בשיחה.

## לפני שמתחילים

- העוזר פועל על **הספרייה שלך** (ספרים שכבר ייבאת) + כלים מורשים.
- **ייבוא/סקייפ מאתר** דורש מצב `LLM_ASSISTANT_MODE=external_allowed` וטופס אישור (HITL) לפני שהעבודה רצה.
- אתרים נתמכים לסקייפ: `novelfull.net`, `novelbin.com`, `freewebnovel.com`, `novellunar.com`.
- טקסט מספרים/אתרים נחשב **מידע**, לא הוראות לעוזר.
- בזמן תשובה: שורת סטטוס חיה, כפתור **Stop** לביטול, והצ'אט נשאר בתחתית אלא אם גללת למעלה.

## מה אפשר לבקש

### 1. ספרייה וחיפוש

| יכולת | כלי (פנימי) |
|--------|-------------|
| רשימת ספרים / סינון לפי כותרת או מחבר | `search_user_books` |
| פרטי ספר | `get_book_details` |
| סיכום ספר שמור / יצירה לפי דרישה | `get_book_summary` → `summarize_book` |
| חיפוש בסיכומים, מטא־דאטה ותוכן פרקים | `search_library_content` |
| רשימת פרקים | `list_available_chapters` |
| קריאת תוכן פרק | `get_chapter_content` |

**דוגמאות:**

```text
אילו ספרים יש לי בספרייה?
```

```text
מצא ספרים של Martial Peak בספרייה שלי
```

```text
תן לי פרטים על הספר Martial Peak
```

```text
חפש בספרייה שלי איפה מוזכר cultivation breakthrough
```

```text
סכם לי את Martial Peak בלי ספוילרים
```

```text
Give me a full plot summary of Martial Peak, spoilers are OK
```

סיכומים נוצרים לפי דרישה ונשמרים. קריאה חוזרת משתמשת במטמון כל עוד תוכן
הפרקים לא השתנה; שינוי/ייבוא פרקים מסמן את הסיכום כלא עדכני ומייצר חדש בבקשה הבאה.

```text
כמה פרקים יש ל־Martial Peak אצלי?
```

```text
תקריא לי בקצרה מה קורה בפרק 10 של Martial Peak
```

### 2. התקדמות קריאה

| יכולת | כלי |
|--------|------|
| איפה עצרתי בספר | `get_reading_progress` |
| פרקים שקראתי לאחרונה | `get_recently_read_chapters` |

**דוגמאות:**

```text
איפה עצרתי ב־Martial Peak?
```

```text
מה קראתי לאחרונה?
```

```text
תראה לי את ההתקדמות שלי בכל הספרים
```

### 3. ניגון / המשך (play / resume)

| יכולת | כלי | הערה |
|--------|------|------|
| התחל פרק | `play_chapter` | מנווט לפרק ומתחיל TTS אוטומטית |
| המשך מאיפה שעצרתי | `resume_book` | לפי progress שמור; מתחיל TTS |

**דוגמאות:**

```text
תנגן את פרק 12 של Martial Peak
```

```text
תמשיך את Martial Peak מאיפה שעצרתי
```

```text
resume my last book
```

אם הדפדפן חוסם autoplay, נגן ה-reader נשאר גלוי ואפשר ללחוץ Play כדי להתחיל.

### 4. הורדת אודיו

| יכולת | כלי | הערה |
|--------|------|------|
| יצירת MP3 לפרק אחד עם ברירות מחדל | `create_chapter_download` | פעולה מהירה לפרק בודד |
| יצירת MP3 לטווח פרקים | `create_audio_download` | טופס אישור עם טווח, provider, voice וקצב |
| סטטוס הורדה | `get_download_status` | |

ברירת המחדל של SAPI היא **Microsoft Zira Desktop במהירות 1.35×** — גם במודאל
ההורדה וגם בטופס האישור של הצ'אט. אחרי אישור טווח:

- כרטיס האישור נעלם (אין בועת “Approved” מיותרת).
- מוצג כרטיס עבודה עם התקדמות פרקים חיה.
- הקובץ יורד אוטומטית כשהעבודה מסתיימת, ונשאר כפתור הורדה חוזרת.
- שם הקובץ כולל שם ספר, טווח פרקים וסיומת ייחודית קצרה, לדוגמה
  `Martial-Peak-chapters-5-12-a1b2c3d4.mp3`.

**דוגמאות:**

```text
תכין לי MP3 של פרק 5 ב־Martial Peak
```

```text
מה הסטטוס של ההורדה האחרונה?
```

```text
Download chapter 3 of Martial Peak as audio
```

```text
Download chapters 5 through 12 of Martial Peak using Edge, Aria voice, at 1.2x
```

### 5. הגדרות אתר ונגן

הכלי `update_ui_settings` משנה רק הגדרות הפיכות ומורשות: theme, גודל גופן,
מהירות ניגון, browser/server engine, provider/voice ומצב highlighting.
שינויי theme/font/highlighting חלים מיד גם ב-reader ובספרייה.

```text
Switch to dark mode, set the reader font to 1.4rem, and use paragraph highlighting
```

```text
Use server playback with Edge voice and play at 1.25x
```

### 6. ייבוא / סקייפ מסאתר (HITL)

| יכולת | כלי | הערה |
|--------|------|------|
| חיפוש כותרת באתרים נתמכים | `search_discovered_books` | מחזיר מועמדים + מקורות מדורגים (`recommended`) |
| ייבוא מועמד discovery (בלי URL) | `import_discovered_book` | טופס אישור; בוחר מקור עשיר בפרקים אם לא צוין |
| הוספת ספר מ־URL | `scrape_book_range` | תמיד מופיע טופס אישור לפני הרצה |

בטופס (גם לייבוא discovery וגם ל־URL):

- **Starting chapter** — מאיזה פרק להתחיל (ברירת מחדל 1)
- **Amount of chapters** — כמה פרקים; ריק = כל הספר  
  אם ביקשת "מ־5 עד 55", העוזר אמור למלא `start=5`, `count=51` (כולל שני הקצוות)

אפשר לתת **שם ספר** (בלי URL) — חיפוש → בחירה → import; או **URL** של עמוד ספר/פרק.

**דוגמאות (כותרת בלי URL):**

```text
Find Rise of the Primordial Godsmith and add it to my library
```

```text
תמצא את Martial Peak באתרים הנתמכים ותייבא לספרייה מתחילת פרק 1
```

**דוגמאות (URL):**

```text
Add this book to my library: https://novelfull.net/martial-peak.html
```

```text
Add this book to my library: https://novelfull.net/martial-peak.html
from chapter 5 to 55
```

```text
תסקרפ את הספר הזה לתוך הספרייה שלי:
https://novelfull.net/martial-peak.html
כל הספר, מתחיל מפרק 1
```

```text
Scrape https://novelbin.com/b/some-slug starting at chapter 10, only 20 chapters
```

אחרי האישור — בדוק את רשימת ה־jobs במסך **Scraper**.

### 7. ייבוא EPUB

במסך **Scraper → Upload EPUB** אפשר להעלות קובץ, לבדוק מטא־דאטה ורשימת פרקים,
ולייבא אותו בחלקים לעבודה עמידה יותר. התקדמות ושגיאות מוצגות בזמן הייבוא.

## מה עדיין לא (בכוונה / בהמשך)

- חיפוש discovery לפי נושא/trope והמלצות סמנטיות (כרגע החיפוש הוא בעיקר לפי כותרת/alias)
- סיכום מועמד discovery לפני ייבוא (סיכומי ספרים שכבר בספרייה כן נתמכים)
- הערכת מספר פרקים מלאה בכל מקור (הדירוג משתמש במטא־דאטה הזמין)
- דיון עשיר ורב־שלבי יותר על ספרים
- כלים הרסניים/יקרים נוספים: מחיקת ספר, overwrite, retry גדול והורדת ספר מלאה
- RAG/embeddings — יתווספו רק אם summary + FTS לא יספיקו
- דילוג על טופס האישור גם כשכל הפרמטרים כבר בפרומפט (HITL נשאר שער אבטחה/עלות)
- אתרים שלא ברשימת האדפטרים

## טיפים לפרומפטים טובים

1. **שם ספר ברור** כשיש כמה דומים בספרייה.
2. לייבוא — אפשר לתת **שם ספר** לחיפוש בכל האתרים הנתמכים, או URL ישיר; ציין
   טווח פרקים באותה הודעה אם ידוע.
3. לסיכום — ציין אם מותר ספוילרים; לשאלת עלילה נקודתית נסח מה לחפש ("איפה X קורה").
4. אם כלי נכשל — בקש צעד הבא ("תציע חלופה" / "תבדוק אם הספר בכלל בספרייה").

## הקשר מסך (ADR-14)

כל הודעה שולחת את העמוד הנוכחי (`path`, וב־reader גם `book_id` / `chapter_id`) כמידע
לעוזר — לא כהוראות. אחרי סקייפ מוצלח מופיע כפתור **Open Scraper** בכרטיס הכלי;
play/resume שולחים כוונת **Play chapter** ומתחילים ניגון אחרי הניווט. רענון רשימת
ה־jobs אוטומטי (לא תפקיד המודל). הורדת אודיו מאושרת שולחת client action מוגבל עם
מזהה job בלבד; ה־frontend מציג התקדמות ומוריד את הקובץ המוכן.

## קישור לתכנון

פירוט ארכיטקטורה וכלים: [llm-planning/README.md](./llm-planning/README.md).

