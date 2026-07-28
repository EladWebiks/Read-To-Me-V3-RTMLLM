# מסמך יכולות — עוזר RTM (Milestone B)

מסמך קצר למה שהעוזר **יודע לעשות עכשיו**, עם דוגמאות פרומפטים.
לא תכנון עתידי — רק מה שעובד בפועל בשיחה.

## לפני שמתחילים

- העוזר פועל על **הספרייה שלך** (ספרים שכבר ייבאת) + כלים מורשים.
- **ייבוא/סקייפ מאתר** דורש מצב `LLM_ASSISTANT_MODE=external_allowed` וטופס אישור (HITL) לפני שהעבודה רצה.
- אתרים נתמכים לסקייפ: `novelfull.net`, `novelbin.com`, `freewebnovel.com`, `novellunar.com`.
- טקסט מספרים/אתרים נחשב **מידע**, לא הוראות לעוזר.

## מה אפשר לבקש

### 1. ספרייה וחיפוש

| יכולת | כלי (פנימי) |
|--------|-------------|
| רשימת ספרים / סינון לפי כותרת או מחבר | `search_user_books` |
| פרטי ספר | `get_book_details` |
| חיפוש בתוך תוכן הפרקים | `search_library_content` |
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
| התחל פרק | `play_chapter` | מעדכן progress ומחזיר כוונת ניגון ללקוח |
| המשך מאיפה שעצרתי | `resume_book` | לפי progress שמור |

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

### 4. הורדת אודיו (פרק בודד)

| יכולת | כלי | הערה |
|--------|------|------|
| יצירת MP3 לפרק אחד | `create_chapter_download` | טווח פרקים מרובים עדיין לא דרך העוזר |
| סטטוס הורדה | `get_download_status` | |

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

### 5. ייבוא / סקייפ מסאתר (HITL)

| יכולת | כלי | הערה |
|--------|------|------|
| הוספת ספר מסאתר נתמך | `scrape_book_range` | תמיד מופיע טופס אישור לפני הרצה |

בטופס:

- **Starting chapter** — מאיזה פרק להתחיל (ברירת מחדל 1)
- **Amount of chapters** — כמה פרקים; ריק = כל הספר  
  אם ביקשת "מ־5 עד 55", העוזר אמור למלא `start=5`, `count=51` (כולל שני הקצוות)

אפשר לתת URL של **עמוד ספר** או של **פרק** — המערכת מתחילה ללכת מפרק ראשון כשצריך.

**דוגמאות:**

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

## מה עדיין לא (בכוונה / בהמשך)

- ייבוא מועמד discovery → HITL scrape בלי URL (חלקית: חיפוש כותרת ב־NovelFull + כלי
  `search_discovered_books` כבר קיים; בחירת מקור חכמה + import עדיין לא)
- הורדת אודיו ל**טווח פרקים** דרך העוזר
- דילוג על טופס האישור גם כשכל הפרמטרים כבר בפרומפט (HITL נשאר שער אבטחה/עלות)
- אתרים שלא ברשימת האדפטרים

## טיפים לפרומפטים טובים

1. **שם ספר ברור** כשיש כמה דומים בספרייה.
2. לסקייפ — **הדבק URL** של אתר נתמך; טווח פרקים באותה הודעה אם ידוע.
3. לשאלות עלילה/נושא — נסח שאילתת חיפוש ("איפה X קורה") ולא רק "סכם לי את הספר" בלי הקשר.
4. אם כלי נכשל — בקש צעד הבא ("תציע חלופה" / "תבדוק אם הספר בכלל בספרייה").

## הקשר מסך (ADR-14)

כל הודעה שולחת את העמוד הנוכחי (`path`, וב־reader גם `book_id` / `chapter_id`) כמידע
לעוזר — לא כהוראות. אחרי סקייפ מוצלח מופיע כפתור **Open Scraper** בכרטיס הכלי;
play/resume יכולים להציע **Open chapter**. רענון רשימת ה־jobs אוטומטי (לא תפקיד המודל).

## קישור לתכנון

פירוט ארכיטקטורה וכלים: [llm-planning/README.md](./llm-planning/README.md).

