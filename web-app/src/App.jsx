import PracticePage, { AttemptsList } from "./practice/PracticePage.jsx";
import React, { useEffect, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  Award,
  BarChart3,
  BookOpen,
  CalendarDays,
  Camera,
  CheckCircle2,
  ChevronRight,
  Clock3,
  GraduationCap,
  Hand,
  Home,
  LineChart,
  Play,
  Repeat2,
  Search,
  Sparkles,
  Star,
  Target,
  Trophy,
  Users,
  Volume2,
} from "lucide-react";
import { getFallbackImageUrl, getSignDefinition, getSignImageUrl } from "./data/signContent";

const navItems = [
  { id: "home", label: "Home", icon: Home },
  { id: "courses", label: "Courses", icon: BookOpen },
  { id: "detail", label: "Sign Detail", icon: Hand },
  { id: "practice", label: "AI Practice", icon: Camera },
  { id: "progress", label: "Progress", icon: BarChart3 },
];

const rawLectures = [
  { title: "Greetings", theme: "Greetings", words: ["HELLO", "BYE", "PLEASE", "THANKYOU", "SORRY", "YES", "NO", "OK", "AGAIN", "HELP"], sentence: "HELLO, MY NAME fs-CHRIS." },
  { title: "Introduction", theme: "Introduction", words: ["I/ME", "YOU", "MY", "YOUR", "NAME", "WHAT", "WHO", "NICE", "MEET", "SAME"], sentence: "YOUR NAME WHAT?" },
  { title: "Numbers", theme: "Numbers", words: ["ZERO", "ONE", "TWO", "THREE", "FOUR", "THIRD", "SIX", "SEVEN", "EIGHT", "NINE"], sentence: "I HAVE TWO BROTHER." },
  { title: "Family 1", theme: "Family 1", words: ["FAMILY", "MOTHER", "FATHER", "SISTER", "BROTHER", "GRANDMOTHER", "GRANDFATHER", "BABY", "CHILD", "PARENTS"], sentence: "MY FAMILY HAVE FOUR PEOPLE." },
  { title: "People", theme: "People", words: ["FRIEND", "TEACHER", "STUDENT", "PERSON", "MAN", "WOMAN", "BOY", "GIRL", "DEAF", "HEARING"], sentence: "MY FRIEND DEAF." },
  { title: "School", theme: "School", words: ["SCHOOL", "CLASS", "LEARN", "STUDY", "BOOK", "PAPER", "PEN", "COMPUTER", "HOMEWORK", "TEST"], sentence: "I STUDY ASL." },
  { title: "Daily Verbs", theme: "Daily Verbs", words: ["GO", "COME", "WANT", "NEED", "LIKE", "DISLIKE", "KNOW", "CONFUSED", "UNDERSTAND", "FINISH"], sentence: "YOU WANT HELP?" },
  { title: "Time 1", theme: "Time 1", words: ["NOW", "TODAY", "TOMORROW", "YESTERDAY", "MORNING", "AFTERNOON", "NIGHT", "WEEK", "MONTH", "YEAR"], sentence: "TOMORROW I GO SCHOOL." },
  { title: "Weekdays", theme: "Weekdays", words: ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY", "EVERYDAY", "SOMETIMES", "ALWAYS"], sentence: "MONDAY I HAVE CLASS." },
  { title: "Colors", theme: "Colors", words: ["RED", "BLUE", "GREEN", "YELLOW", "BLACK", "WHITE", "BROWN", "PINK", "PURPLE", "ORANGE"], sentence: "I LIKE BLUE." },
  { title: "Food 1", theme: "Food 1", words: ["LUNCH", "EAT", "DRINK", "WATER", "MILK", "COFFEE", "TEA", "BREAD", "SANDWICH", "EGG"], sentence: "MORNING I DRINK COFFEE." },
  { title: "Food 2", theme: "Food 2", words: ["APPLE", "BANANA", "PEACH", "MEAT", "TURKEY", "FISH", "VEGETABLE", "SALAD", "SOUP", "COOK"], sentence: "I WANT EAT FISH." },
  { title: "Home", theme: "Home", words: ["HOME", "HOUSE", "ROOM", "KITCHEN", "BATHROOM", "BED", "CHAIR", "TABLE", "DOOR", "WINDOW"], sentence: "MY HOME HAVE TWO ROOM." },
  { title: "Places", theme: "Places", words: ["HERE", "THERE", "SHOP", "RESTAURANT", "HOSPITAL", "LIBRARY", "PARK", "BANK", "CHURCH", "WORK"], sentence: "I GO STORE." },
  { title: "Transportation", theme: "Transportation", words: ["CAR", "BUS", "TRAIN", "AIRPLANE", "BICYCLE", "WALK", "DRIVE", "RIDE", "ARRIVE", "LEAVE"], sentence: "I DRIVE WORK." },
  { title: "Directions", theme: "Directions", words: ["WHERE", "LEFT", "RIGHT", "FRONT", "BACK", "NEAR", "FAR", "INSIDE", "OUTSIDE", "CROSS"], sentence: "LIBRARY WHERE?" },
  { title: "Weather", theme: "Weather", words: ["WEATHER", "SUN", "RAIN", "SNOW", "WIND", "CLOUD", "HOT", "COLD", "WARM", "COOL"], sentence: "TODAY WEATHER COLD." },
  { title: "Emotions", theme: "Emotions", words: ["HAPPY", "SAD", "ANGRY", "TIRED", "SICK", "EXCITED", "SCARED", "WORRY", "BORED", "FINE"], sentence: "I TIRED TODAY." },
  { title: "Body", theme: "Body", words: ["HEAD", "EYES", "EAR", "NOSE", "MOUTH", "HANDS", "ARM", "SHOULDER", "FINGER", "HEART"], sentence: "MY HEAD HURT." },
  { title: "Health", theme: "Health", words: ["DOCTOR", "NURSE", "MEDICINE", "PAIN", "HURT", "HEADACHE", "COUGH", "HEALTH", "APPOINTMENT", "PATIENT"], sentence: "I NEED DOCTOR." },
  { title: "Clothes", theme: "Clothes", words: ["CLOTHES", "SHIRT", "PANTS", "SHOES", "SOCKS", "JACKET", "HAT", "DRESS", "GLASSES", "WATCH"], sentence: "MY SHOES BLACK." },
  { title: "Shopping", theme: "Shopping", words: ["BUY", "PAY", "MONEY", "PRICE", "CHEAP", "EXPENSIVE", "SHOP", "CREDITCARD", "WALLET", "CHECK"], sentence: "THAT PRICE EXPENSIVE." },
  { title: "Work", theme: "Work", words: ["WORKSHOP", "WORK", "BOSS", "OFFICE", "MEETING", "EMAIL", "PHONE", "BUSY", "BREAK", "FINISH"], sentence: "I WORK OFFICE." },
  { title: "Interests", theme: "Interests", words: ["PLAY", "GAME", "MUSIC", "MOVIE", "DANCE", "READ", "DRAW", "EXERCISE", "SWIM", "TRAVEL"], sentence: "I LIKE MOVIE." },
  { title: "Sports", theme: "Sports", words: ["SPORTS", "BALL", "BASKETBALL", "FOOTBALL", "BASEBALL", "SOCCER", "RUN", "WIN", "LOSE", "TEAM"], sentence: "MY TEAM WIN." },
  { title: "Animals", theme: "Animals", words: ["ANIMAL", "DOG", "CAT", "BIRD", "FISH", "HORSE", "COW", "PIG", "BEAR", "MONKEY"], sentence: "I HAVE CAT." },
  { title: "Question Words", theme: "Question Words", words: ["WHAT", "WHO", "WHERE", "WHEN", "WHY", "HOW", "WHICH", "MANY", "MUCH", "ASK"], sentence: "YOU GO WHERE?" },
  { title: "Description", theme: "Description", words: ["BIG", "SMALL", "TALL", "SHORTPERSON", "OLD", "YOUNG", "NEW", "GOOD", "BAD", "PRETTY"], sentence: "YOUR HOUSE BIG." },
  { title: "Travel", theme: "Travel", words: ["TRAVEL", "VACATION", "HOTEL", "TRIP", "PASSPORT", "TICKET", "ADDRESS", "BAG", "VISIT", "CAMERA"], sentence: "SUMMER I TRAVEL." },
  { title: "Review", theme: "Review", words: ["REMEMBER", "FORGETFUL", "PRACTICE", "SIGN", "SLOW", "FAST", "AGAIN", "READY", "WAIT", "SEE"], sentence: "PLEASE SIGN SLOW AGAIN." },
];

const slugOverrides = {
  "I/ME": "me",
  "THANKYOU": "thank-you",
  "THANK-YOU": "thank-you",
  "GOODBYE": "bye",
  "DONT-LIKE": "dont-like",
  "DONT-KNOW": "dont-know",
  "ORANGE-FRUIT": "orange",
  "FINISH-WORK": "finish-work",
  "SEE-YOU-LATER": "see-you-later",
  "HOW-MANY": "how-many",
  "HOW-MUCH": "how-much",
  "DO-DO": "do-do",
  "FS-CHRIS": "chris",
  "I": "me",
  "HAVE": "have",
  "STORE": "shop",
  "SPORT": "sports",
};

const wordDisplayOverrides = {
  "I/ME": "I / me",
  "THANKYOU": "thank you",
  "THANK-YOU": "thank you",
  "OK": "OK",
  "CREDITCARD": "credit card",
  "SHORTPERSON": "short person",
  "FS-CHRIS": "fs-Chris",
};

const referenceTargetOverrides = {
  "I/ME": "I_ME",
  "I": "I_ME",
};

function glossToSlug(gloss) {
  const key = gloss.toUpperCase();
  return slugOverrides[key] ?? key.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
}

function glossToReferenceTarget(gloss) {
  const key = gloss.toUpperCase();
  return referenceTargetOverrides[key] ?? key;
}

function glossToWord(gloss) {
  const key = gloss.toUpperCase();
  return wordDisplayOverrides[key] ?? gloss.replace(/^fs-/i, "fs-").replace(/-/g, " ").toLowerCase();
}

function sentenceToTokens(sentence) {
  return sentence
    .replace(/[,.?]/g, " ")
    .split(/\s+/)
    .map((token) => token.trim())
    .filter(Boolean);
}

function buildSign(gloss, lecture, lectureIndex, wordIndex) {
  const slug = glossToSlug(gloss);
  const word = glossToWord(gloss);
  return {
    word,
    gloss,
    slug,
    level: "Beginner",
    type: lecture.theme,

    photoUrl: getSignImageUrl(slug, lectureIndex),
    fallbackPhotoUrl: getFallbackImageUrl(lectureIndex),
    signaslUrl: `https://www.signasl.org/sign/${slug}`,
    referenceTarget: glossToReferenceTarget(gloss),
    prompt: `Practice the sign for ${word.toLowerCase()} from the SignASL reference video.`,
    description: getSignDefinition(slug, word),
    metrics: ["Hand shape", "Motion path", "Timing"],
    lectureId: `lesson-${lectureIndex + 1}`,
  };
}

const lectureCatalog = rawLectures.map((lecture, lectureIndex) => ({
  ...lecture,
  id: `lesson-${lectureIndex + 1}`,
  number: lectureIndex + 1,
  signs: lecture.words.map((word, wordIndex) => buildSign(word, lecture, lectureIndex, wordIndex)),
  sentenceTokens: sentenceToTokens(lecture.sentence),
}));

const vocabulary = lectureCatalog.flatMap((lecture) => lecture.signs);

function classNames(...items) { return items.filter(Boolean).join(" "); }

function App() {
  const [activePage, setActivePage] = useState("home");
  const [selectedSignIndex, setSelectedSignIndex] = useState(0);
  const [selectedLectureIndex, setSelectedLectureIndex] = useState(0);
  return (
    <div className="min-h-screen bg-[linear-gradient(135deg,#f8fbff_0%,#edf7ff_45%,#ffffff_100%)] text-slate-900">
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-64 border-r border-blue-100 bg-white/85 px-5 py-6 shadow-sm backdrop-blur xl:block">
        <Brand />
        <nav className="mt-9 space-y-2">
          {navItems.map((item) => (
            <NavButton key={item.id} item={item} active={activePage === item.id} onClick={() => setActivePage(item.id)} />
          ))}
        </nav>
        <div className="mt-10 rounded-lg border border-blue-100 bg-blue-50 p-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-blue-800">
            <Sparkles size={17} />
            Lesson Path
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-600">Alphabet basics, daily words, guided practice, then review.</p>
        </div>
      </aside>

      <main className="xl:pl-64">
        <TopBar activePage={activePage} setActivePage={setActivePage} />
        <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
          {activePage === "home" && <HomePage setActivePage={setActivePage} />}
          {activePage === "courses" && <CoursesPage setActivePage={setActivePage} setSelectedSignIndex={setSelectedSignIndex} setSelectedLectureIndex={setSelectedLectureIndex} />}
          {activePage === "detail" && <SignDetailPage selectedSignIndex={selectedSignIndex} selectedLecture={lectureCatalog[selectedLectureIndex]} setSelectedSignIndex={setSelectedSignIndex} setActivePage={setActivePage} />}
          {activePage === "practice" && (
            <PracticePage vocabulary={vocabulary} initialSign={vocabulary[selectedSignIndex]} ReferenceVideo={SignASLVideo} />
          )}
          {activePage === "progress" && <ProgressPage setActivePage={setActivePage} />}
        </div>
      </main>
    </div>
  );
}

function Brand() {
  return (
    <div className="flex items-center gap-3">
      <div className="grid h-11 w-11 place-items-center rounded-lg bg-blue-600 text-white shadow-soft">
        <Hand size={24} />
      </div>
      <div>
        <div className="text-lg font-bold tracking-tight">SIGN COACH</div>
      </div>
    </div>
  );
}

function NavButton({ item, active, onClick }) {
  const Icon = item.icon;
  return (
    <button
      onClick={onClick}
      className={classNames(
        "flex w-full items-center gap-3 rounded-lg px-3 py-3 text-left text-sm font-semibold transition",
        active ? "bg-blue-600 text-white shadow-soft" : "text-slate-600 hover:bg-blue-50 hover:text-blue-700",
      )}
    >
      <Icon size={19} />
      {item.label}
    </button>
  );
}

function TopBar({ activePage, setActivePage }) {
  const pageTitle = navItems.find((item) => item.id === activePage)?.label ?? "Home";
  return (
    <header className="sticky top-0 z-10 border-b border-blue-100 bg-white/82 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-4 sm:px-6 lg:px-8">
        <div className="flex min-w-0 items-center gap-3">
          <div className="xl:hidden">
            <Brand />
          </div>
          <div className="hidden xl:block">
            <h1 className="text-xl font-bold tracking-tight">{pageTitle}</h1>
            <p className="text-sm text-slate-500">Learn, practice, review</p>
          </div>
        </div>
        <div className="hidden flex-1 justify-center md:flex xl:hidden">
          <div className="flex rounded-lg border border-blue-100 bg-blue-50 p-1">
            {navItems.slice(0, 5).map((item) => (
              <button
                key={item.id}
                onClick={() => setActivePage(item.id)}
                className={classNames(
                  "rounded-md px-3 py-2 text-xs font-semibold transition",
                  activePage === item.id ? "bg-white text-blue-700 shadow-sm" : "text-slate-600",
                )}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="hidden items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-500 sm:flex">
            <Search size={16} />
            Search lessons
          </div>
          <div className="grid h-10 w-10 place-items-center rounded-lg bg-slate-900 text-sm font-bold text-white">CL</div>
        </div>
      </div>
      <div className="flex gap-2 overflow-x-auto px-4 pb-3 md:hidden">
        {navItems.map((item) => (
          <button
            key={item.id}
            onClick={() => setActivePage(item.id)}
            className={classNames(
              "whitespace-nowrap rounded-lg px-3 py-2 text-xs font-semibold",
              activePage === item.id ? "bg-blue-600 text-white" : "bg-white text-slate-600",
            )}
          >
            {item.label}
          </button>
        ))}
      </div>
    </header>
  );
}

function SectionTitle({ eyebrow, title, action, onAction }) {
  return (
    <div className="mb-4 flex items-end justify-between gap-3">
      <div>
        <p className="text-sm font-semibold uppercase tracking-wide text-blue-600">{eyebrow}</p>
        <h2 className="mt-1 text-2xl font-bold tracking-tight text-slate-950">{title}</h2>
      </div>
      {action && (
        <button onClick={onAction} className="hidden items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-soft sm:flex">
          {action}
          <ChevronRight size={16} />
        </button>
      )}
    </div>
  );
}

function StatCard({ icon: Icon, label, value, tone = "blue" }) {
  const tones = {
    blue: "bg-blue-50 text-blue-700 border-blue-100",
    emerald: "bg-emerald-50 text-emerald-700 border-emerald-100",
    amber: "bg-amber-50 text-amber-700 border-amber-100",
    slate: "bg-slate-50 text-slate-700 border-slate-200",
  };
  return (
    <div className="rounded-lg border border-blue-100 bg-white p-5 shadow-sm">
      <div className={classNames("grid h-10 w-10 place-items-center rounded-lg border", tones[tone])}>
        <Icon size={20} />
      </div>
      <div className="mt-4 text-2xl font-bold tracking-tight">{value}</div>
      <div className="mt-1 text-sm font-medium text-slate-500">{label}</div>
    </div>
  );
}

function HomePage({ setActivePage }) {
  return <section className="space-y-6"><SectionTitle eyebrow="SignCoach" title="Learn a sign. Give it a try." />
    <p className="text-slate-600">Browse the courses and reference videos, then record a four-second practice attempt.</p>
    <div className="flex gap-4"><button className="rounded-lg bg-blue-600 px-6 py-3 text-white" onClick={() => setActivePage("courses")}>Browse courses</button>
    <button className="rounded-lg border border-blue-300 px-6 py-3" onClick={() => setActivePage("practice")}>Start practice</button></div>
    <AttemptsList />
  </section>;
}

function CoursesPage({ setActivePage, setSelectedSignIndex, setSelectedLectureIndex }) {
  function open(lectureIndex, sign) {
    setSelectedLectureIndex(lectureIndex);
    setSelectedSignIndex(vocabulary.indexOf(sign));
    setActivePage("detail");
  }
  return <section className="space-y-5">
    <SectionTitle eyebrow="Course library" title="30-lesson beginner learning path" />
    <p className="text-slate-500">Explore any lecture. Demo recording supports the words listed on the practice page.</p>
    {lectureCatalog.map((lecture, index) => <details key={lecture.id} className="rounded-xl border border-blue-100 bg-white p-5" open={index === 0 ? true : undefined}>
      <summary className="cursor-pointer text-xl font-bold">Lecture {lecture.number}: {lecture.title}</summary>
      <p className="my-3 text-sm text-slate-500">Reading example: {lecture.sentence}</p>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{lecture.signs.map(sign => <button key={sign.gloss} className="overflow-hidden rounded-lg border border-slate-100 text-left hover:shadow-md" onClick={() => open(index, sign)}>
        <WordImage sign={sign} className="h-32 w-full" /><div className="p-4"><h3 className="text-lg font-bold">{sign.word}</h3><p className="mt-2 text-sm text-slate-500">{sign.description}</p></div>
      </button>)}</div>
    </details>)}
  </section>;
}

function WordImage({ sign, className }) {
  const [src, setSrc] = useState(sign.photoUrl);

  useEffect(() => {
    setSrc(sign.photoUrl);
  }, [sign.photoUrl]);

  return (
    <img
      src={src}
      alt={`${sign.word} visual meaning`}
      className={classNames("bg-slate-100 object-cover", className)}
      loading="lazy"
      onError={() => {
        if (src !== sign.fallbackPhotoUrl) {
          setSrc(sign.fallbackPhotoUrl);
        }
      }}
    />
  );
}

function SignDetailPage({ selectedSignIndex, selectedLecture = lectureCatalog[0], setSelectedSignIndex, setActivePage }) {
  const selectedSign = vocabulary[selectedSignIndex];
  const localSignIndex = Math.max(
    0,
    selectedLecture.signs.findIndex((item) => item.slug === selectedSign?.slug && item.gloss === selectedSign?.gloss),
  );
  const sign = selectedLecture.signs[localSignIndex] ?? selectedLecture.signs[0];
  const previousLocalIndex = Math.max(0, localSignIndex - 1);
  const nextLocalIndex = Math.min(selectedLecture.signs.length - 1, localSignIndex + 1);
  const isFirstSign = localSignIndex === 0;
  const isLastSign = localSignIndex === selectedLecture.signs.length - 1;

  function setLectureSign(localIndex) {
    const nextSign = selectedLecture.signs[localIndex];
    const globalIndex = vocabulary.findIndex((item) => item.lectureId === nextSign.lectureId && item.gloss === nextSign.gloss);
    setSelectedSignIndex(Math.max(0, globalIndex));
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[0.95fr_1.05fr]">
      <section className="rounded-lg border border-blue-100 bg-white p-5 shadow-sm">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-sm font-semibold uppercase tracking-wide text-blue-600">Lecture {selectedLecture.number} word</p>
            <h2 className="mt-2 text-4xl font-bold tracking-tight">{sign.word}</h2>
            <p className="mt-3 max-w-xl leading-7 text-slate-600">{sign.description}</p>
          </div>
          <button className="grid h-11 w-11 place-items-center rounded-lg bg-blue-50 text-blue-700" aria-label="Play pronunciation">
            <Volume2 size={20} />
          </button>
        </div>

        <WordImage sign={sign} className="mt-7 h-80 w-full rounded-lg border border-slate-100" />

        <div className="mt-7 rounded-lg border border-blue-100 bg-blue-50 px-4 py-3 text-sm font-semibold text-blue-800">
          Study each word in this lecture. The final next button opens AI practice.
        </div>
      </section>

      <section className="rounded-lg border border-blue-100 bg-white p-5 shadow-sm">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-xl font-bold">SignASL demonstration</h3>
        </div>
        <SignASLVideo sign={sign} />
        <p className="mt-4 rounded-lg bg-blue-50 px-4 py-3 text-sm leading-6 text-blue-900">{sign.prompt}</p>
        <div className="mt-5 grid gap-3 sm:grid-cols-3">
          <SmallMetric label="Hand shape" value={sign.metrics[0]} />
          <SmallMetric label="Motion" value={sign.metrics[1]} />
          <SmallMetric label="Timing" value={sign.metrics[2]} />
        </div>
      </section>

      <section className="lg:col-span-2">
        <div className="flex items-center justify-between rounded-lg border border-blue-100 bg-white p-3 shadow-sm">
          <button
            aria-label="Previous sign"
            onClick={() => setLectureSign(previousLocalIndex)}
            disabled={isFirstSign}
            className={classNames("grid h-12 w-12 place-items-center rounded-lg transition", isFirstSign ? "cursor-not-allowed bg-slate-100 text-slate-300" : "bg-slate-100 text-slate-700 hover:bg-slate-200")}
          >
            <ArrowLeft size={20} />
          </button>
          <div className="text-center">
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">Lecture words</div>
            <div className="mt-1 text-sm font-bold text-blue-700">
              {localSignIndex + 1} / {selectedLecture.signs.length}
            </div>
          </div>
          <button
            aria-label={isLastSign ? "Practice" : "Next sign"}
            onClick={() => {
              if (isLastSign) {
                setActivePage("practice");
              } else {
                setLectureSign(nextLocalIndex);
              }
            }}
            className={classNames("flex h-12 items-center justify-center gap-2 rounded-lg bg-blue-600 text-white shadow-soft transition hover:bg-blue-700", isLastSign ? "px-4 text-sm font-bold" : "w-12")}
          >
            {isLastSign ? (
              <>
                <Camera size={18} />
                Practice
              </>
            ) : (
              <ArrowRight size={20} />
            )}
          </button>
        </div>
      </section>
    </div>
  );
}

function SmallMetric({ label, value }) {
  return (
    <div className="rounded-lg border border-slate-100 bg-slate-50 p-4">
      <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">{label}</div>
      <div className="mt-1 text-sm font-bold text-slate-800">{value}</div>
    </div>
  );
}

function SignASLVideo({ sign, compact = false }) {
  const [videoUrl, setVideoUrl] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(false);
    setVideoUrl(null);

    fetch(`/api/signasl/video/${sign.slug}`)
      .then((response) => {
        if (!response.ok) {
          throw new Error(`SignASL API ${response.status}`);
        }
        return response.json();
      })
      .then((data) => {
        if (cancelled) return;
        if (data.video_url) {
          setVideoUrl(data.video_url);
        } else {
          setError(true);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setError(true);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [sign.slug]);

  return (
    <div className={classNames("overflow-hidden rounded-lg border border-blue-100 bg-slate-50", compact ? "aspect-video" : "aspect-video")}>
      {videoUrl ? (
        <video key={videoUrl} src={videoUrl} controls playsInline className="h-full w-full bg-black object-contain" />
      ) : (
        <div className="grid h-full place-items-center p-6 text-center">
          <div>
            <div className="mx-auto grid h-12 w-12 place-items-center rounded-lg bg-blue-50 text-blue-700">
              <Play size={22} />
            </div>
            <p className="mt-3 text-sm font-semibold text-slate-700">{loading ? "Loading first SignASL video..." : "Video source unavailable"}</p>
            {error && (
              <a href={sign.signaslUrl} target="_blank" rel="noreferrer" className="mt-2 inline-block text-sm font-bold text-blue-700">
                Open SignASL
              </a>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function ProgressPage() { return <AttemptsList />; }

export default App;
