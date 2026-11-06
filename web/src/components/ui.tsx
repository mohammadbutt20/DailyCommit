import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
} from "react";

export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}

export function Card({
  children,
  className,
  padded = true,
}: {
  children: ReactNode;
  className?: string;
  padded?: boolean;
}) {
  return (
    <section
      className={cx(
        "rounded-xl border border-line bg-surface shadow-[0_1px_0_0_#ffffff08_inset]",
        padded && "p-5",
        className,
      )}
    >
      {children}
    </section>
  );
}

export function CardHeader({
  title,
  hint,
  action,
}: {
  title: ReactNode;
  hint?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="mb-4 flex items-center justify-between gap-3">
      <div className="min-w-0">
        <h2 className="text-sm font-semibold tracking-tight text-fg">{title}</h2>
        {hint && <p className="mt-0.5 text-xs text-muted">{hint}</p>}
      </div>
      {action}
    </div>
  );
}

type ButtonVariant = "primary" | "secondary" | "ghost";
type ButtonSize = "sm" | "md";

const BUTTON_VARIANTS: Record<ButtonVariant, string> = {
  primary:
    "bg-accent text-accent-ink hover:bg-[#5be3a2] shadow-[0_0_0_1px_#3fd68f,0_6px_20px_-8px_#3fd68f99]",
  secondary: "border border-line-strong bg-raised text-fg hover:border-faint hover:bg-[#1c2128]",
  ghost: "text-muted hover:bg-raised hover:text-fg",
};

const BUTTON_SIZES: Record<ButtonSize, string> = {
  sm: "h-8 px-3 text-xs",
  md: "h-9 px-4 text-sm",
};

export function Button({
  variant = "primary",
  size = "md",
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant; size?: ButtonSize }) {
  return (
    <button
      className={cx(
        "inline-flex shrink-0 items-center justify-center gap-2 rounded-lg font-medium whitespace-nowrap transition-colors disabled:cursor-not-allowed disabled:opacity-45",
        BUTTON_VARIANTS[variant],
        BUTTON_SIZES[size],
        className,
      )}
      {...props}
    />
  );
}

const FIELD =
  "h-9 w-full rounded-lg border border-line-strong bg-sunken px-3 text-sm text-fg placeholder:text-faint outline-none transition-colors focus:border-accent focus:ring-2 focus:ring-accent-soft";

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cx(FIELD, className)} {...props} />;
}

export function Select({ className, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={cx(FIELD, "pr-8", className)} {...props} />;
}

type Tone = "neutral" | "accent" | "warn" | "danger";

const TONES: Record<Tone, string> = {
  neutral: "bg-raised text-muted border-line-strong",
  accent: "bg-accent-soft text-accent border-[#3fd68f33]",
  warn: "bg-warn-soft text-warn border-[#f2b84b33]",
  danger: "bg-danger-soft text-danger border-[#f0646f33]",
};

export function Badge({
  tone = "neutral",
  children,
  className,
}: {
  tone?: Tone;
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[11px] leading-none font-medium",
        TONES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

export function Difficulty({ level }: { level: string }) {
  const tone: Tone = level === "easy" ? "accent" : level === "medium" ? "warn" : "danger";
  return (
    <Badge tone={tone} className="capitalize">
      {level}
    </Badge>
  );
}

// Muted tints so avatars read as people, not status colors.
const AVATAR_TINTS = [
  "bg-[#24324a] text-[#9cb8e8]",
  "bg-[#3a2a45] text-[#cfa6e6]",
  "bg-[#43302a] text-[#e8b79c]",
  "bg-[#2a3d3d] text-[#9ad6d0]",
  "bg-[#3d3a26] text-[#ddd08f]",
  "bg-[#43293a] text-[#e8a3c4]",
];

export function Avatar({
  name,
  src,
  size = "md",
  ring,
}: {
  name: string;
  src?: string | null;
  size?: "sm" | "md" | "lg";
  ring?: "accent" | "none";
}) {
  let hash = 0;
  for (const ch of name) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
  const initials = name
    .split(/[\s_]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]!.toUpperCase())
    .join("");
  const sizes = { sm: "h-6 w-6 text-[10px]", md: "h-8 w-8 text-xs", lg: "h-10 w-10 text-sm" };
  const ringClass = ring === "accent" && "ring-2 ring-accent ring-offset-2 ring-offset-surface";
  if (src) {
    return (
      // Discord CDN avatars; next/image would need remotePatterns for no real gain at this size.
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={src}
        alt=""
        aria-hidden
        referrerPolicy="no-referrer"
        className={cx("shrink-0 rounded-full object-cover", sizes[size], ringClass)}
      />
    );
  }
  return (
    <span
      aria-hidden
      className={cx(
        "inline-flex shrink-0 items-center justify-center rounded-full font-semibold",
        AVATAR_TINTS[hash % AVATAR_TINTS.length],
        sizes[size],
        ringClass,
      )}
    >
      {initials || "?"}
    </span>
  );
}

export function Segmented<T extends string>({
  value,
  options,
  onChange,
}: {
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
}) {
  return (
    <div className="inline-flex rounded-lg border border-line bg-sunken p-0.5 text-xs">
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          className={cx(
            "rounded-md px-2.5 py-1 font-medium transition-colors",
            value === o.value ? "bg-raised text-fg shadow-sm" : "text-muted hover:text-fg",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Eyebrow({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <p
      className={cx(
        "font-mono text-[11px] font-medium tracking-[0.08em] text-faint uppercase",
        className,
      )}
    >
      {children}
    </p>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-lg border border-dashed border-line px-4 py-6 text-center text-sm text-faint">
      {children}
    </p>
  );
}

export function ErrorText({ error }: { error: unknown }) {
  if (!error) return null;
  return (
    <p className="mt-3 rounded-lg border border-[#f0646f33] bg-danger-soft px-3 py-2 text-sm text-danger">
      {error instanceof Error ? error.message : "Something went wrong"}
    </p>
  );
}

export function Spinner({ className }: { className?: string }) {
  return (
    <span
      aria-hidden
      className={cx(
        "inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-r-transparent",
        className,
      )}
    />
  );
}

export function Loading() {
  return (
    <div className="flex items-center gap-2 py-16 text-sm text-faint">
      <Spinner />
      Loading…
    </div>
  );
}

/** A placeholder block shown while content loads (instead of a "Loading…" flash). */
export function Skeleton({ className }: { className?: string }) {
  return <span aria-hidden className={cx("block animate-pulse rounded bg-raised", className)} />;
}
