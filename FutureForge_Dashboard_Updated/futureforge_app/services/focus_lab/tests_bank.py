"""
Focus Lab self-assessment bank. Every test = short multiple-choice questionnaire on a 4-point frequency scale.

Each question is (statement, reverse):  reverse=False -> more frequent is better; reverse=True -> more frequent is
worse (e.g. "I check my phone mid-task"). Points per answer are 0-3 (flipped for reverse). Behavioural / productivity
self-assessment only — NOT a medical or psychological assessment.
"""
from __future__ import annotations

OPTIONS = ["Rarely", "Sometimes", "Often", "Almost always"]


def _t(title, icon, desc, area, qs, actions):
    return {"title": title, "icon": icon, "description": desc, "area": area,
            "questions": [(q.lstrip("-"), q.startswith("-")) for q in qs], "actions": actions}


# A question starting with "-" is a reverse-scored one (frequent = worse).
_DEFS = {
"focus_consistency": _t("Focus Consistency Test", "🧠", "How steadily you can hold attention on one task across a work or study session.", "focus consistency", [
    "I can stay on one task for 25 minutes or more without switching.",
    "-I check my phone or other tabs while working.",
    "I start a session with one clear task in mind.",
    "-I lose track of what I was doing after an interruption.",
    "My focus stays similar from the start to the end of a long session.",
    "I take planned breaks instead of drifting off task."],
    ["Use structured focus sessions (25–50 minutes) with one clear task each.", "Reduce digital distractions: silence notifications and keep the phone out of reach.",
     "Write down the single task before you start a session.", "Take planned short breaks so focus is renewed, not forced."]),
"time_management": _t("Time Management Test", "⏱️", "How well you plan, estimate and use your available time.", "time management", [
    "I plan my day or week before starting work.",
    "-I underestimate how long tasks take.",
    "I finish important tasks before their deadlines.",
    "-I spend time on low-priority things while important ones wait.",
    "I leave buffer time between tasks.",
    "I review at the end of the day what I completed."],
    ["Plan tomorrow's top 3 tasks the evening before.", "Add 25% buffer to your time estimates.", "Time-block important work in your best hours.", "Do a 5-minute end-of-day review."]),
"study_habit": _t("Study Habit Test", "📚", "How regular and effective your study routine is.", "study habits", [
    "I study at roughly the same time each day.",
    "-I postpone studying until the last moment.",
    "I revise material soon after learning it.",
    "I study in a place with few distractions.",
    "I set a specific goal for each study session.",
    "I practise or self-test instead of only re-reading."],
    ["Fix a daily study slot and protect it.", "Revise within 24 hours of learning something new.", "Set one concrete goal per session.", "Use self-testing (questions, flashcards) over re-reading."]),
"workload_management": _t("Workload Management Test", "💼", "How manageable your current workload and meeting load feel day to day.", "workload management", [
    "I can finish my planned work within normal working hours.",
    "-My meetings crowd out focused work time.",
    "I can say no or renegotiate when my plate is full.",
    "-I carry unfinished tasks over from day to day.",
    "I take a real break during the workday."],
    ["List all tasks and mark what is truly urgent.", "Block meeting-free time for focused work.", "Renegotiate or delegate one task this week.", "Protect a proper lunch/break window."]),
"digital_distraction": _t("Digital Distraction Test", "📱", "How much screens and notifications pull you away from what you intend to do.", "digital distraction", [
    "-Notifications interrupt me while I work or study.",
    "-I open social media without deciding to.",
    "I keep my phone away during focused work.",
    "-I lose more time online than I planned.",
    "I use app limits or focus modes."],
    ["Turn off non-essential notifications.", "Keep the phone in another room during focus blocks.", "Set app limits for social media.", "Schedule specific times to check messages."]),
"routine_consistency": _t("Routine Consistency Test", "🔄", "How steady your daily routine is across days.", "routine consistency", [
    "I wake up at a similar time every day.",
    "I have a regular time for study or work.",
    "-My schedule changes a lot from day to day.",
    "I eat meals at fairly regular times.",
    "I follow a wind-down routine before bed.",
    "I keep my routine steady on weekends too."],
    ["Anchor your day with a fixed wake-up time.", "Keep one regular work/study block daily.", "Build a simple evening wind-down routine.", "Keep weekend routines close to weekdays."]),
"task_prioritization": _t("Task Prioritization Test", "🎯", "How clearly you decide what to do first.", "task prioritization", [
    "I identify my most important task before starting the day.",
    "-I start with easy tasks and leave important ones for later.",
    "I can tell urgent tasks from important ones.",
    "-I feel unsure what to work on next.",
    "I drop or postpone low-value tasks."],
    ["Pick 1–3 must-do tasks each morning.", "Sort tasks by urgent vs important.", "Do the hardest important task first.", "Drop or defer tasks with low value."]),
"learning_consistency": _t("Learning Consistency Test", "📖", "How regularly you learn, revise and practise.", "learning consistency", [
    "I learn something at a regular pace each week.",
    "I revise earlier topics at planned intervals.",
    "-I go days without touching my learning material.",
    "I complete assignments or exercises on time.",
    "I track my learning progress.",
    "I practise what I learn, not only read it."],
    ["Schedule short daily learning blocks.", "Use spaced revision (1 day, 3 days, 7 days).", "Track weekly progress in a simple log.", "Practise with exercises after each topic."]),
"habit_consistency": _t("Habit Consistency Test", "🌱", "How reliably you keep your daily habits.", "habit consistency", [
    "I keep my daily habits on busy days too.",
    "-I skip habits when I feel tired or busy.",
    "I attach new habits to existing routines.",
    "I track my habits (app, notebook or calendar).",
    "I restart quickly after missing a day.",
    "I exercise or move regularly."],
    ["Start with one small habit and keep it easy.", "Attach habits to an existing routine.", "Track streaks visibly.", "Follow a 'never miss twice' rule."]),
"sleep_routine": _t("Sleep Routine Test", "😴", "How regular your sleep schedule and pre-sleep habits are.", "sleep routine", [
    "I go to bed at a similar time every night.",
    "I wake up at a similar time every day.",
    "-I use screens in bed before sleeping.",
    "-I sleep noticeably less on busy days.",
    "My sleep space is dark, quiet and comfortable."],
    ["Keep a fixed sleep and wake time.", "Avoid screens 30–60 minutes before bed.", "Keep the bedroom cool, dark and quiet.", "Plan work so late nights are the exception."]),
"lifestyle_consistency": _t("Lifestyle Consistency Test", "🏃", "How consistent your activity, rest and recovery are.", "lifestyle consistency", [
    "I do some physical activity on most days.",
    "I take rest days or recovery time when needed.",
    "-My activity level swings between very high and very low.",
    "I drink water and eat at regular times.",
    "I spend time outdoors or away from screens daily."],
    ["Aim for a small activity every day (a walk counts).", "Schedule recovery time like any other task.", "Keep meal and water timing regular.", "Add a daily screen-free outdoor break."]),
"work_focus": _t("Work Focus Test", "🎯", "How well you protect focused time at work.", "work focus", [
    "I get long uninterrupted blocks for deep work.",
    "-Emails and chat messages break my concentration.",
    "I decide when to check email/chat instead of reacting.",
    "I end the workday with my main task done.",
    "-I multitask across several tasks at once."],
    ["Block 60–90 minutes of deep work daily.", "Check email and chat at fixed times.", "Do one task at a time.", "Set your top task before opening messages."]),
"remote_work_focus": _t("Remote Work Focus Test", "💻", "How well you stay focused and structured while working remotely.", "remote-work focus", [
    "I have a dedicated workspace or routine to start work.",
    "-Household or home distractions interrupt my work.",
    "I have clear start and end times for my workday.",
    "I schedule deep-work hours separate from client calls.",
    "-I work through breaks or late into the evening."],
    ["Create a start-of-work ritual and workspace.", "Set fixed start and end times.", "Separate deep work from calls.", "Protect breaks and an evening cut-off."]),
"workload_balance": _t("Workload Balance Test", "📋", "How balanced your project and client load is.", "workload balance", [
    "I can say no when my capacity is full.",
    "-I take on more projects than I can comfortably finish.",
    "I keep buffer time for unexpected client requests.",
    "I know my weekly capacity in hours.",
    "-Deadlines from different clients collide."],
    ["Calculate your weekly capacity in hours.", "Add buffer for unexpected requests.", "Stagger deadlines across clients.", "Politely decline or reschedule when full."]),
"team_workload": _t("Team Workload Test", "👥", "How evenly and sustainably work is spread across the team.", "team workload", [
    "Tasks are distributed fairly among team members.",
    "-A few people carry most of the pending work.",
    "The team reviews workload regularly.",
    "-Meetings take time from delivery work.",
    "Blocked tasks are raised and resolved quickly."],
    ["Review workload per member weekly.", "Rebalance tasks from overloaded members.", "Cut or shorten low-value meetings.", "Escalate blockers early."]),
"screen_time_management": _t("Screen-Time Management Test", "⏳", "How intentionally you manage total screen time.", "screen-time management", [
    "I know roughly how many hours I spend on screens daily.",
    "-My screen time is higher than I want it to be.",
    "I take regular screen breaks (look away, stand up).",
    "I set screen-free periods each day.",
    "-I use screens late into the night."],
    ["Check your daily screen-time report weekly.", "Use the 20-20-20 eye-break habit.", "Set a screen-free hour each day.", "Set a screen cut-off before bedtime."]),
"digital_habit": _t("Digital Habit Test", "🔌", "How healthy and intentional your everyday digital habits are.", "digital habits", [
    "-I reach for my phone automatically when idle.",
    "I use devices for a purpose, then put them down.",
    "-I scroll for long stretches without noticing.",
    "I keep meals and conversations device-free.",
    "I regularly clean up apps and notifications."],
    ["Replace idle scrolling with a planned alternative.", "Decide the purpose before unlocking the phone.", "Keep meals device-free.", "Remove apps you no longer use."]),
"gaming_routine": _t("Gaming Routine Test", "🎮", "How balanced your gaming schedule is with the rest of your day.", "gaming routine", [
    "I play at planned times rather than open-ended.",
    "-Gaming pushes back my sleep or meals.",
    "I warm up before competitive play.",
    "I balance gaming with study, work or exercise.",
    "-I keep playing after my performance drops."],
    ["Set a planned gaming window.", "Stop for the night when performance drops.", "Warm up before ranked play.", "Keep sleep and meals protected."]),
"session_management": _t("Session Management Test", "🕹️", "How you structure session length and breaks.", "session management", [
    "I take a short break during long sessions.",
    "-I play or work for hours without stopping.",
    "I decide the session length before starting.",
    "I stretch, hydrate or rest my eyes between sessions.",
    "-Late in a session my decisions get sloppy."],
    ["Set a session timer before you start.", "Take a 5-minute break each hour.", "Stretch and hydrate between sessions.", "End sessions when decision quality drops."]),
"project_risk": _t("Project Risk Assessment", "📊", "How well your project is tracking against deadlines and scope.", "project risk", [
    "The project has clear milestones with dates.",
    "-Deadlines are getting tight with much work pending.",
    "Risks and blockers are listed and reviewed.",
    "-Scope changes without adjusting the plan.",
    "Progress is visible to the whole team."],
    ["Break work into dated milestones.", "Keep a short risk/blocker list and review weekly.", "Re-plan when scope changes.", "Share progress updates regularly."]),
"work_productivity": _t("Work Productivity Assessment", "📈", "A quick look at how productively your work time is used.", "work productivity", [
    "I complete the tasks I plan each day.",
    "-A lot of my day goes on unplanned work.",
    "I have energy for the whole workday.",
    "I know which tasks create the most value.",
    "-I end the day unsure what I achieved."],
    ["Plan a realistic daily task list.", "Identify your highest-value tasks.", "Protect energy: sleep, breaks, movement.", "Log daily wins to see progress."]),
"routine_stability": _t("Routine Stability Test", "📅", "How stable your weekly structure is.", "routine stability", [
    "My weekly schedule follows a recognisable pattern.",
    "-Unplanned events regularly derail my day.",
    "I plan the coming week in advance.",
    "I keep fixed time for exercise or personal habits.",
    "I recover quickly when my routine is disrupted."],
    ["Do a 10-minute weekly plan.", "Fix recurring blocks in your calendar.", "Keep one flexible slot for surprises.", "Restart the routine the next day after a disruption."]),
}
TESTS = _DEFS
