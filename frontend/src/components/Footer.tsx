export function Footer() {
  return (
    <footer className="border-t border-zinc-200 bg-white">
      <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6 lg:px-8">
        <div className="flex flex-col gap-6 sm:flex-row sm:items-start sm:justify-between">
          <div className="max-w-sm">
            <p className="text-sm font-semibold text-zinc-900">Universal File Converter</p>
            <p className="mt-2 text-sm leading-relaxed text-zinc-500">
              Convert documents, spreadsheets, images and archives on your own machine.
              Files are processed temporarily and deleted automatically.
            </p>
          </div>

          <div className="flex gap-10 text-sm">
            <div>
              <p className="font-medium text-zinc-900">Backend</p>
              <ul className="mt-2 space-y-1.5 text-zinc-500">
                <li>
                  <a
                    href="http://localhost:8000/docs"
                    target="_blank"
                    rel="noreferrer"
                    className="rounded transition-colors hover:text-zinc-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-900"
                  >
                    API docs
                  </a>
                </li>
                <li>
                  <a
                    href="http://localhost:8000/api/health"
                    target="_blank"
                    rel="noreferrer"
                    className="rounded transition-colors hover:text-zinc-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-900"
                  >
                    Health
                  </a>
                </li>
              </ul>
            </div>
          </div>
        </div>

        <p className="mt-8 border-t border-zinc-200 pt-6 text-xs text-zinc-400">
          Runs locally. No accounts, no uploads to third parties, temporary files
          auto-deleted after the retention window.
        </p>
      </div>
    </footer>
  );
}
