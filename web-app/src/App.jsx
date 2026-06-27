import React, { useEffect, useMemo, useRef, useState } from "react";
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
  ListChecks,
  Play,
  Repeat2,
  Search,
  Sparkles,
  Target,
  Trophy,
  Users,
  Volume2,
} from "lucide-react";
import helloSignImage from "./assets/sign-hello.svg";
import thanksSignImage from "./assets/sign-thanks.svg";
import waterSignImage from "./assets/sign-water.svg";

const navItems = [
  { id: "home", label: "Home", icon: Home },
  { id: "courses", label: "Courses", icon: BookOpen },
  { id: "detail", label: "Sign Detail", icon: Hand },
  { id: "practice", label: "AI Practice", icon: Camera },
  { id: "progress", label: "Progress", icon: BarChart3 },
];

const lessons = [
  { label: "Letters", count: 26, progress: 42, color: "bg-blue-600", icon: "A" },
  { label: "Common Words", count: 48, progress: 68, color: "bg-emerald-500", icon: "Hi" },
  { label: "Daily Scenes", count: 32, progress: 25, color: "bg-amber-500", icon: "Day" },
  { label: "AI Practice", count: 12, progress: 58, color: "bg-sky-500", icon: "AI" },
];

const feedback = [
  "Raise your right hand slightly higher.",
  "Keep your palm facing forward.",
  "Good hand shape. Hold for one more second.",
  "Move closer to the center frame.",
];

const vocabulary = [
  {
    word: "Telephone",
    modelLabel: "callonphone",
    slug: "telephone",
    level: "Beginner",
    type: "Action Words",
    accuracy: 94,
    image: helloSignImage,
    photoUrl: "https://images.unsplash.com/photo-1512428559087-560fa5ceab42?auto=format&fit=crop&w=900&h=620&q=80",
    signaslUrl: "https://www.signasl.org/sign/telephone",
    prompt: "Practice the sign for telephone from the SignASL reference video.",
    description: "A device used to call someone.",
    metrics: ["Phone hand", "Near face", "Clear pose"],
  },
  {
    word: "Bath",
    slug: "bath",
    level: "Beginner",
    type: "Daily Words",
    accuracy: 88,
    image: waterSignImage,
    photoUrl: "https://images.unsplash.com/photo-1584622650111-993a426fbf0a?auto=format&fit=crop&w=900&h=620&q=80",
    signaslUrl: "https://www.signasl.org/sign/bath",
    prompt: "Practice the sign for bath from the SignASL reference video.",
    description: "Washing the body in water.",
    metrics: ["Two hands", "Body area", "Repeated motion"],
  },
  {
    word: "Apple",
    slug: "apple",
    level: "Beginner",
    type: "Object Words",
    accuracy: 84,
    image: helloSignImage,
    photoUrl: "https://images.unsplash.com/photo-1560806887-1e4cd0b6cbd6?auto=format&fit=crop&w=900&h=620&q=80",
    signaslUrl: "https://www.signasl.org/sign/apple",
    prompt: "Practice the sign for apple from the SignASL reference video.",
    description: "A round fruit.",
    metrics: ["Handshape", "Near cheek", "Hold"],
  },
  {
    word: "Bye",
    slug: "bye",
    level: "Beginner",
    type: "Greeting Words",
    accuracy: 91,
    image: thanksSignImage,
    photoUrl: "https://images.unsplash.com/photo-1511632765486-a01980e01a18?auto=format&fit=crop&w=900&h=620&q=80",
    signaslUrl: "https://www.signasl.org/sign/bye",
    prompt: "Practice the sign for bye from the SignASL reference video.",
    description: "A farewell.",
    metrics: ["Open hand", "Small wave", "Clear motion"],
  },
  {
    word: "Car",
    slug: "car",
    level: "Beginner",
    type: "Object Words",
    accuracy: 90,
    image: helloSignImage,
    photoUrl: "https://images.unsplash.com/photo-1533473359331-0135ef1b58bf?auto=format&fit=crop&w=900&h=620&q=80",
    signaslUrl: "https://www.signasl.org/sign/car",
    prompt: "Practice the sign for car from the SignASL reference video.",
    description: "A road vehicle.",
    metrics: ["Two hands", "Steering motion", "Centered"],
  },
];

function classNames(...items) {
  return items.filter(Boolean).join(" ");
}

function createSessionId() {
  return globalThis.crypto?.randomUUID?.() ?? `session-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function App() {
  const [activePage, setActivePage] = useState("home");
  const [selectedSignIndex, setSelectedSignIndex] = useState(0);

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
          {activePage === "courses" && <CoursesPage setActivePage={setActivePage} setSelectedSignIndex={setSelectedSignIndex} />}
          {activePage === "detail" && <SignDetailPage selectedSignIndex={selectedSignIndex} setSelectedSignIndex={setSelectedSignIndex} setActivePage={setActivePage} />}
          {activePage === "practice" && <PracticePage initialSignIndex={selectedSignIndex} />}
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
        <div className="text-lg font-bold tracking-tight">SignLearn</div>
        <div className="text-xs font-medium uppercase text-slate-500">ASL Coach</div>
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
  return (
    <div className="space-y-7">
      <section className="overflow-hidden rounded-lg border border-blue-100 bg-white shadow-soft">
        <div className="grid gap-0 lg:grid-cols-[1.15fr_0.85fr]">
          <div className="bg-[linear-gradient(135deg,#2563eb_0%,#0ea5e9_55%,#ecfeff_100%)] p-6 text-white sm:p-8">
            <div className="inline-flex items-center gap-2 rounded-lg bg-white/20 px-3 py-2 text-sm font-semibold">
              <CalendarDays size={16} />
              Today: 18 minutes planned
            </div>
            <h1 className="mt-6 max-w-xl text-3xl font-bold tracking-tight sm:text-4xl">One sign today. Keep your streak alive.</h1>
            <p className="mt-4 max-w-2xl text-base leading-8 text-blue-50">
              Practice a tiny lesson, get instant encouragement, and come back tomorrow a little stronger. SignLearn turns ASL basics into short daily wins, so beginners can learn at school, at home, or with a parent beside them.
            </p>
            <div className="mt-7 flex flex-wrap gap-3">
              <button onClick={() => setActivePage("practice")} className="flex items-center gap-2 rounded-lg bg-white px-5 py-3 text-sm font-bold text-blue-700 shadow-soft">
                <Play size={17} />
                Start Practice
              </button>
              <button onClick={() => setActivePage("courses")} className="flex items-center gap-2 rounded-lg border border-white/50 px-5 py-3 text-sm font-bold text-white">
                <BookOpen size={17} />
                Browse Courses
              </button>
            </div>
          </div>
          <div className="video-noise relative min-h-[320px] p-6">
            <LearningVisual />
          </div>
        </div>
      </section>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard icon={Clock3} label="Learning days" value="12" />
        <StatCard icon={Target} label="Today accuracy" value="86%" tone="emerald" />
        <StatCard icon={Trophy} label="Mastered signs" value="34" tone="amber" />
        <StatCard icon={Repeat2} label="Review queue" value="8" tone="slate" />
      </div>

      <section>
        <SectionTitle eyebrow="Today's learning" title="Clear path for a 15-minute session" action="AI Practice" onAction={() => setActivePage("practice")} />
        <div className="grid gap-4 lg:grid-cols-3">
          {["Warm up alphabet", "Practice common words", "Review weak signs"].map((title, index) => (
            <div key={title} className="rounded-lg border border-blue-100 bg-white p-5 shadow-sm">
              <div className="flex items-center justify-between">
                <div className="grid h-10 w-10 place-items-center rounded-lg bg-blue-50 text-sm font-bold text-blue-700">{index + 1}</div>
                <span className="text-sm font-semibold text-slate-400">{index === 0 ? "5 min" : index === 1 ? "7 min" : "3 min"}</span>
              </div>
              <h3 className="mt-5 text-lg font-bold">{title}</h3>
              <p className="mt-2 text-sm leading-6 text-slate-500">{["A, B, C, D", "Hello, thanks, help", "Water, yes, no"][index]}</p>
              <div className="mt-5 h-2 rounded-full bg-slate-100">
                <div className="h-2 rounded-full bg-blue-600" style={{ width: `${[80, 54, 32][index]}%` }} />
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function LearningVisual() {
  return (
    <div className="relative h-full min-h-[280px] rounded-lg border border-white/70 bg-white/78 p-5 shadow-soft">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-sm font-semibold text-slate-500">Current sign</div>
          <div className="mt-1 text-2xl font-bold text-slate-950">Telephone</div>
        </div>
        <div className="flex items-center gap-1 rounded-lg bg-emerald-50 px-3 py-2 text-sm font-bold text-emerald-700">
          <CheckCircle2 size={17} />
          94%
        </div>
      </div>
      <div className="camera-grid mt-5 grid min-h-[170px] place-items-center rounded-lg border border-blue-100 bg-white">
        <div className="relative h-32 w-32">
          <div className="absolute left-10 top-3 h-16 w-12 rounded-full border-4 border-blue-500 bg-blue-50" />
          <div className="absolute left-7 top-20 h-16 w-20 rounded-t-full border-4 border-blue-500 bg-blue-50" />
          <div className="absolute left-1 top-16 h-8 w-16 -rotate-12 rounded-full border-4 border-emerald-500 bg-emerald-50" />
          <div className="absolute right-0 top-14 h-8 w-16 rotate-[-32deg] rounded-full border-4 border-amber-500 bg-amber-50" />
        </div>
      </div>
      <div className="mt-4 grid grid-cols-3 gap-3 text-center text-sm font-semibold">
        <div className="rounded-lg bg-blue-50 py-3 text-blue-700">Palm</div>
        <div className="rounded-lg bg-emerald-50 py-3 text-emerald-700">Wrist</div>
        <div className="rounded-lg bg-amber-50 py-3 text-amber-700">Hold</div>
      </div>
    </div>
  );
}

function CoursesPage({ setActivePage, setSelectedSignIndex }) {
  const [lessonOpen, setLessonOpen] = useState(true);

  return (
    <div className="space-y-7">
      <SectionTitle eyebrow="Course library" title="Lesson 1 contains every word in this demo" />
      <section className="rounded-lg border border-blue-100 bg-white shadow-sm">
        <button onClick={() => setLessonOpen((open) => !open)} className="flex w-full items-center justify-between gap-4 p-5 text-left">
          <div className="flex items-center gap-4">
            <div className="grid h-14 w-14 place-items-center rounded-lg bg-blue-600 text-lg font-black text-white">L1</div>
            <div>
              <h3 className="text-xl font-bold">Lesson 1: Everyday Starter Signs</h3>
              <p className="mt-1 text-sm text-slate-500">{vocabulary.length} words for the one-minute demo practice flow</p>
            </div>
          </div>
          <ChevronRight className={classNames("shrink-0 text-blue-600 transition", lessonOpen && "rotate-90")} size={22} />
        </button>

        {lessonOpen && (
          <div className="border-t border-blue-100 p-5">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <h3 className="text-lg font-bold">Lesson words</h3>
              <button onClick={() => setActivePage("practice")} className="flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white">
                <Camera size={16} />
                Practice Lesson 1
              </button>
            </div>
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {vocabulary.map((item, index) => (
                <button
                  key={item.word}
                  onClick={() => {
                    setSelectedSignIndex(index);
                    setActivePage("detail");
                  }}
                  className="overflow-hidden rounded-lg border border-slate-100 bg-slate-50 text-left transition hover:-translate-y-1 hover:shadow-soft"
                >
                  <img src={item.photoUrl} alt={item.word} className="h-32 w-full object-cover" />
                  <div className="p-4">
                    <div className="flex items-center justify-between gap-3">
                      <h4 className="text-lg font-bold">{item.word}</h4>
                      <span className="rounded-lg bg-blue-50 px-2.5 py-1 text-xs font-bold text-blue-700">{item.accuracy}%</span>
                    </div>
                    <p className="mt-2 line-clamp-2 text-sm leading-6 text-slate-500">{item.description}</p>
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

function SignDetailPage({ selectedSignIndex, setSelectedSignIndex, setActivePage }) {
  const sign = vocabulary[selectedSignIndex % vocabulary.length];
  const previousIndex = (selectedSignIndex - 1 + vocabulary.length) % vocabulary.length;
  const nextIndex = (selectedSignIndex + 1) % vocabulary.length;

  return (
    <div className="grid gap-6 lg:grid-cols-[0.95fr_1.05fr]">
      <section className="rounded-lg border border-blue-100 bg-white p-5 shadow-sm">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-sm font-semibold uppercase tracking-wide text-blue-600">Common word</p>
            <h2 className="mt-2 text-4xl font-bold tracking-tight">{sign.word}</h2>
            <p className="mt-3 max-w-xl leading-7 text-slate-600">{sign.description}</p>
          </div>
          <button className="grid h-11 w-11 place-items-center rounded-lg bg-blue-50 text-blue-700" aria-label="Play pronunciation">
            <Volume2 size={20} />
          </button>
        </div>

        <img src={sign.photoUrl} alt={`${sign.word} visual meaning`} className="mt-7 h-80 w-full rounded-lg border border-slate-100 object-cover" />

        <div className="mt-7 flex flex-wrap gap-3">
          <button onClick={() => setActivePage("practice")} className="flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-3 text-sm font-bold text-white shadow-soft">
            <Camera size={17} />
            Practice this sign
          </button>
          <button className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-5 py-3 text-sm font-bold text-slate-700">
            <ListChecks size={17} />
            Add to review
          </button>
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
          <button aria-label="Previous sign" onClick={() => setSelectedSignIndex(previousIndex)} className="grid h-12 w-12 place-items-center rounded-lg bg-slate-100 text-slate-700 transition hover:bg-slate-200">
            <ArrowLeft size={20} />
          </button>
          <div className="text-center">
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">Swipe through signs</div>
            <div className="mt-1 text-sm font-bold text-blue-700">
              {selectedSignIndex + 1} / {vocabulary.length}
            </div>
          </div>
          <button aria-label="Next sign" onClick={() => setSelectedSignIndex(nextIndex)} className="grid h-12 w-12 place-items-center rounded-lg bg-blue-600 text-white shadow-soft transition hover:bg-blue-700">
            <ArrowRight size={20} />
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

    fetch(`http://127.0.0.1:8000/api/signasl/video/${sign.slug}`)
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

function PracticePage({ initialSignIndex = 0 }) {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const sessionRef = useRef(createSessionId());
  const [cameraOn, setCameraOn] = useState(false);
  const [score, setScore] = useState(0);
  const [tipIndex, setTipIndex] = useState(0);
  const [capturedImage, setCapturedImage] = useState(null);
  const [practiceIndex, setPracticeIndex] = useState(initialSignIndex);
  const [completedSlugs, setCompletedSlugs] = useState(() => new Set());
  const [showCompletion, setShowCompletion] = useState(false);
  const [prediction, setPrediction] = useState("Waiting");
  const [confidence, setConfidence] = useState(0);
  const [apiMessage, setApiMessage] = useState("Start the camera to connect with the ASL model.");
  const [targetSupported, setTargetSupported] = useState(true);
  const [apiOnline, setApiOnline] = useState(null);

  const currentSignIndex = ((practiceIndex % vocabulary.length) + vocabulary.length) % vocabulary.length;
  const currentSign = vocabulary[currentSignIndex];

  useEffect(() => {
    setPracticeIndex(initialSignIndex);
    setCapturedImage(null);
    setScore(0);
    setPrediction("Waiting");
    setConfidence(0);
    setApiMessage("Start the camera to connect with the ASL model.");
    sessionRef.current = createSessionId();
  }, [initialSignIndex]);

  useEffect(() => {
    if (!cameraOn || capturedImage) {
      return undefined;
    }
    const timer = window.setInterval(() => {
      sendPracticeFrame();
      setTipIndex((current) => (current + 1) % feedback.length);
    }, 850);
    return () => window.clearInterval(timer);
  }, [cameraOn, capturedImage, currentSign.word]);

  useEffect(() => {
    if (cameraOn && (score >= 80 || confidence >= 70) && !capturedImage) {
      captureCurrentFrame();
    }
  }, [cameraOn, score, confidence, capturedImage]);

  useEffect(() => {
    return () => {
      streamRef.current?.getTracks().forEach((track) => track.stop());
    };
  }, []);

  async function startCamera() {
    if (!navigator.mediaDevices?.getUserMedia) {
      setCameraOn(false);
      return;
    }
    const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
    streamRef.current = stream;
    if (videoRef.current) {
      videoRef.current.srcObject = stream;
      setCameraOn(true);
      setCapturedImage(null);
      setScore(0);
      setPrediction("Collecting");
      setConfidence(0);
      setApiMessage("Collecting motion window...");
      setApiOnline(true);
      sessionRef.current = createSessionId();
    }
  }

  async function sendPracticeFrame() {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || !video.videoWidth || !video.videoHeight) {
      return;
    }
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const context = canvas.getContext("2d");
    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    const image = canvas.toDataURL("image/jpeg", 0.72);

    try {
      const response = await fetch("http://127.0.0.1:8000/api/practice/frame", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          image,
          target: currentSign.modelLabel ?? currentSign.word,
          session_id: sessionRef.current,
        }),
      });
      if (!response.ok) {
        throw new Error(`API ${response.status}`);
      }
      const data = await response.json();
      setApiOnline(true);
      setTargetSupported(data.target_supported);
      setPrediction(data.prediction ?? "Collecting");
      setConfidence(Math.round((data.confidence ?? 0) * 100));
      setScore(data.score ?? 0);
      setApiMessage(data.message ?? "Model response received.");
    } catch (error) {
      setApiOnline(false);
      setApiMessage("Model API is offline. Start the Python backend on port 8000.");
      setPrediction("API offline");
      setConfidence(0);
      setScore(0);
    }
  }

  function captureCurrentFrame() {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || !video.videoWidth || !video.videoHeight) {
      return;
    }
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const context = canvas.getContext("2d");
    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    setCapturedImage(canvas.toDataURL("image/png"));
    setCompletedSlugs((current) => {
      const next = new Set(current);
      next.add(currentSign.slug);
      if (next.size === vocabulary.length) {
        setShowCompletion(true);
      }
      return next;
    });
  }

  function nextPractice() {
    setPracticeIndex((current) => current + 1);
    setCapturedImage(null);
    setScore(0);
    setTipIndex(0);
    setPrediction("Waiting");
    setConfidence(0);
    setApiMessage("Start the camera to connect with the ASL model.");
    sessionRef.current = createSessionId();
  }

  function restartLesson() {
    setCompletedSlugs(new Set());
    setShowCompletion(false);
    setPracticeIndex(0);
    setCapturedImage(null);
    setScore(0);
    setTipIndex(0);
    setPrediction("Waiting");
    setConfidence(0);
    setApiMessage("Start the camera to connect with the ASL model.");
    sessionRef.current = createSessionId();
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm font-semibold uppercase tracking-wide text-blue-600">AI practice</p>
          <h2 className="mt-1 text-2xl font-bold tracking-tight text-slate-950">Practice: {currentSign.word}</h2>
        </div>
        <button onClick={nextPractice} className="flex items-center gap-2 rounded-lg border border-blue-100 bg-white px-4 py-2 text-sm font-bold text-blue-700 shadow-sm">
          Skip
          <ArrowRight size={16} />
        </button>
      </div>

      <div className="grid gap-3 md:grid-cols-4">
        <CompactStatus label="Score" value={score} tone={score >= 80 || confidence >= 70 ? "emerald" : "blue"} />
        <CompactStatus label="Prediction" value={prediction} tone={score >= 80 || confidence >= 70 ? "emerald" : apiOnline === false ? "amber" : "blue"} />
        <CompactStatus label="Confidence" value={`${confidence}%`} tone={confidence >= 70 ? "emerald" : "slate"} />
        <CompactStatus label="Done" value={`${completedSlugs.size}/${vocabulary.length}`} tone={completedSlugs.has(currentSign.slug) ? "emerald" : "slate"} />
      </div>

      <div className="grid gap-4 xl:grid-cols-[0.95fr_1.05fr]">
        <PracticePanel title="Learn from SignASL" icon={Hand} compact>
          <SignASLVideo sign={currentSign} compact />
          <p className="mt-3 rounded-lg bg-blue-50 px-3 py-2 text-sm leading-6 text-blue-900">{currentSign.prompt}</p>
        </PracticePanel>

        <PracticePanel title="Your camera" icon={Camera} compact>
          <div className="relative aspect-video overflow-hidden rounded-lg border border-blue-100 bg-slate-950">
            <video ref={videoRef} autoPlay playsInline muted className={classNames("h-full w-full object-cover", cameraOn ? "block" : "hidden")} />
            {!cameraOn && (
              <div className="video-noise grid h-full place-items-center text-center">
                <div>
                  <div className="mx-auto grid h-12 w-12 place-items-center rounded-lg bg-white text-blue-700 shadow-soft">
                    <Camera size={24} />
                  </div>
                  <p className="mt-3 text-sm font-semibold text-slate-700">Start camera to practice</p>
                </div>
              </div>
            )}
            <div className="pointer-events-none absolute inset-4 rounded-lg border-2 border-dashed border-white/70" />
            <div className="absolute left-3 top-3 rounded-lg bg-black/55 px-3 py-1.5 text-xs font-semibold text-white">Live landmarks</div>
            {capturedImage && (
              <div className="absolute right-3 top-3 flex items-center gap-2 rounded-lg bg-emerald-500 px-3 py-1.5 text-xs font-bold text-white">
                <CheckCircle2 size={15} />
                Captured
              </div>
            )}
          </div>
          <canvas ref={canvasRef} className="hidden" />
          <button onClick={startCamera} className="mt-3 flex w-full items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-bold text-white shadow-soft">
            <Camera size={17} />
            {cameraOn ? "Restart check" : "Start camera"}
          </button>
        </PracticePanel>
      </div>

      <section className="rounded-lg border border-blue-100 bg-white p-4 shadow-sm">
        <div className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
          <div>
            <div className="flex items-center gap-2">
              <div className={classNames("grid h-9 w-9 place-items-center rounded-lg", capturedImage ? "bg-emerald-50 text-emerald-700" : "bg-blue-50 text-blue-700")}>
                {capturedImage ? <CheckCircle2 size={19} /> : <Target size={19} />}
              </div>
              <div>
                <h3 className="font-bold">{capturedImage ? "Action saved. You can move on." : "Realtime feedback"}</h3>
                <p className="text-sm text-slate-500">
                  {capturedImage
                    ? `Score reached ${score}. Next: ${vocabulary[(practiceIndex + 1) % vocabulary.length].word}`
                    : targetSupported
                      ? apiMessage
                      : `${currentSign.word} is not in this checkpoint. Choose a trained word.`}
                </p>
              </div>
            </div>
            <div className="mt-3 grid gap-2 sm:grid-cols-4">
              {["Right wrist", "Left shoulder", "Palm angle", "Movement path"].map((item, index) => (
                <div key={item} className="rounded-lg bg-slate-50 px-3 py-2">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-bold text-slate-600">{item}</span>
                    <span className={classNames("h-2.5 w-2.5 rounded-full", score > 72 + index * 5 ? "bg-emerald-500" : "bg-amber-500")} />
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="flex items-center gap-3">
            {capturedImage ? (
              <>
                <img src={capturedImage} alt="Captured correct practice action" className="h-28 w-40 rounded-lg border border-emerald-100 object-cover" />
                <button onClick={nextPractice} className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-emerald-600 px-4 py-3 text-sm font-bold text-white shadow-soft">
                  Next practice
                  <ChevronRight size={16} />
                </button>
              </>
            ) : null}
          </div>
        </div>
      </section>

      {showCompletion && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/40 px-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-lg bg-white p-6 text-center shadow-soft">
            <div className="mx-auto grid h-14 w-14 place-items-center rounded-lg bg-emerald-50 text-emerald-700">
              <Trophy size={28} />
            </div>
            <h3 className="mt-5 text-2xl font-black tracking-tight">Today's practice is complete</h3>
            <p className="mt-3 text-sm leading-6 text-slate-600">
              Great work. You finished every sign in Lesson 1. Keep the streak going tomorrow.
            </p>
            <div className="mt-6 grid gap-3 sm:grid-cols-2">
              <button onClick={() => setShowCompletion(false)} className="rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm font-bold text-slate-700">
                Review results
              </button>
              <button onClick={restartLesson} className="rounded-lg bg-blue-600 px-4 py-3 text-sm font-bold text-white shadow-soft">
                Practice again
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function CompactStatus({ label, value, tone }) {
  const tones = {
    blue: "bg-blue-50 text-blue-700 border-blue-100",
    emerald: "bg-emerald-50 text-emerald-700 border-emerald-100",
    amber: "bg-amber-50 text-amber-700 border-amber-100",
    slate: "bg-slate-50 text-slate-700 border-slate-200",
  };
  return (
    <div className={classNames("rounded-lg border px-4 py-3 shadow-sm", tones[tone])}>
      <div className="text-xs font-bold uppercase tracking-wide opacity-75">{label}</div>
      <div className="mt-1 truncate text-xl font-black tracking-tight">{value}</div>
    </div>
  );
}

function PracticePanel({ title, icon: Icon, children, compact = false }) {
  return (
    <section className={classNames("rounded-lg border border-blue-100 bg-white shadow-sm", compact ? "p-4" : "p-5")}>
      <div className={classNames("flex items-center gap-2", compact ? "mb-3" : "mb-4")}>
        <div className="grid h-9 w-9 place-items-center rounded-lg bg-blue-50 text-blue-700">
          <Icon size={18} />
        </div>
        <h3 className={classNames("font-bold", compact ? "text-lg" : "text-xl")}>{title}</h3>
      </div>
      {children}
    </section>
  );
}

function Hint({ label, status, done }) {
  return (
    <div className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-3">
      <span className="text-sm font-semibold text-slate-600">{label}</span>
      <span className={classNames("text-sm font-bold", done ? "text-emerald-600" : "text-amber-600")}>{status}</span>
    </div>
  );
}

function ProgressPage({ setActivePage }) {
  const mastered = ["Hello", "Thanks", "Yes", "No", "A", "B", "C", "Family"];
  const review = ["Water", "Help", "School", "Friend"];

  const chart = useMemo(() => [48, 58, 55, 72, 78, 82, 86], []);

  return (
    <div className="space-y-7">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard icon={CalendarDays} label="Study streak" value="12 days" />
        <StatCard icon={LineChart} label="Average accuracy" value="86%" tone="emerald" />
        <StatCard icon={Award} label="Mastered words" value="34" tone="amber" />
        <StatCard icon={Users} label="Parent sessions" value="5" tone="slate" />
      </div>

      <section className="grid gap-5 lg:grid-cols-[1.2fr_0.8fr]">
        <div className="rounded-lg border border-blue-100 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-xl font-bold">Weekly accuracy</h3>
            <span className="rounded-lg bg-emerald-50 px-3 py-2 text-sm font-bold text-emerald-700">+12%</span>
          </div>
          <div className="mt-6 flex h-64 items-end gap-3">
            {chart.map((value, index) => (
              <div key={index} className="flex flex-1 flex-col items-center gap-2">
                <div className="flex h-52 w-full items-end rounded-lg bg-blue-50">
                  <div className="w-full rounded-lg bg-blue-600" style={{ height: `${value}%` }} />
                </div>
                <span className="text-xs font-semibold text-slate-400">{["M", "T", "W", "T", "F", "S", "S"][index]}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-lg border border-blue-100 bg-white p-5 shadow-sm">
          <h3 className="text-xl font-bold">Learning goal</h3>
          <div className="mt-5 rounded-lg bg-blue-50 p-5">
            <div className="text-sm font-semibold text-blue-700">This week</div>
            <div className="mt-2 text-3xl font-black text-slate-950">24 / 30</div>
            <div className="mt-1 text-sm text-slate-500">practice windows completed</div>
            <div className="mt-5 h-3 rounded-full bg-white">
              <div className="h-3 rounded-full bg-blue-600" style={{ width: "80%" }} />
            </div>
          </div>
          <button onClick={() => setActivePage("practice")} className="mt-5 flex w-full items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-3 text-sm font-bold text-white shadow-soft">
            <GraduationCap size={17} />
            Continue practice
          </button>
        </div>
      </section>

      <section className="grid gap-5 lg:grid-cols-2">
        <WordList title="Mastered vocabulary" words={mastered} tone="emerald" />
        <WordList title="Review next" words={review} tone="amber" />
      </section>
    </div>
  );
}

function WordList({ title, words, tone }) {
  return (
    <div className="rounded-lg border border-blue-100 bg-white p-5 shadow-sm">
      <h3 className="text-xl font-bold">{title}</h3>
      <div className="mt-4 flex flex-wrap gap-3">
        {words.map((word) => (
          <span
            key={word}
            className={classNames(
              "rounded-lg px-3 py-2 text-sm font-bold",
              tone === "emerald" ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700",
            )}
          >
            {word}
          </span>
        ))}
      </div>
    </div>
  );
}

export default App;
