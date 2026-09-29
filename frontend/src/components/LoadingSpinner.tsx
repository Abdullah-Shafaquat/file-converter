interface LoadingSpinnerProps {
  size?: "sm" | "md" | "lg";
  className?: string;
  label?: string;
}

/**
 * Accessible spinner. The label is exposed to screen readers via role=status
 * and the visual ring is hidden from them.
 */
export function LoadingSpinner({
  size = "md",
  className = "",
  label = "Loading",
}: LoadingSpinnerProps) {
  const dimension = { sm: "h-4 w-4", md: "h-6 w-6", lg: "h-10 w-10" }[size];

  return (
    <span
      role="status"
      aria-live="polite"
      className={`inline-flex items-center gap-2 ${className}`}
    >
      <svg
        className={`${dimension} animate-spin text-zinc-900 motion-reduce:animate-none`}
        viewBox="0 0 24 24"
        fill="none"
        aria-hidden="true"
      >
        <circle
          className="opacity-20"
          cx="12"
          cy="12"
          r="10"
          stroke="currentColor"
          strokeWidth="3"
        />
        <path
          className="opacity-90"
          fill="currentColor"
          d="M12 2a10 10 0 0 1 10 10h-3a7 7 0 0 0-7-7z"
        />
      </svg>
      <span className="sr-only">{label}</span>
    </span>
  );
}
