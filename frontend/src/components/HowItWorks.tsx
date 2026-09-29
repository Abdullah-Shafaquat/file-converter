const STEPS = [
  {
    title: "Upload",
    body: "Drag your file in. It stays on your machine — nothing is sent to a third party.",
  },
  {
    title: "Select format",
    body: "We only offer the targets that will genuinely work for your file type.",
  },
  {
    title: "Convert",
    body: "The engine streams your file and reports real progress as it works.",
  },
  {
    title: "Download",
    body: "Grab the result. Both files are deleted automatically afterwards.",
  },
] as const;

export function HowItWorks() {
  return (
    <section id="how-it-works" aria-labelledby="how-heading" className="mt-20 scroll-mt-20 sm:mt-28">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <h2
          id="how-heading"
          className="text-center text-2xl font-semibold tracking-tight text-zinc-900 sm:text-3xl"
        >
          How it works
        </h2>

        <ol className="mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((step, index) => (
            <li key={step.title} className="relative">
              <div className="flex items-center gap-3">
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-zinc-900 text-sm font-semibold text-white">
                  {index + 1}
                </span>
                {index < STEPS.length - 1 && (
                  <span
                    aria-hidden="true"
                    className="hidden h-px flex-1 bg-gradient-to-r from-zinc-300 to-transparent lg:block"
                  />
                )}
              </div>
              <h3 className="mt-4 text-sm font-semibold text-zinc-900">{step.title}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-zinc-500">{step.body}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
