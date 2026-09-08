import { cn } from "@/lib/utils"

type KSignalProps = {
  className?: string
  label?: string
  monochrome?: boolean
}

export function KSignal({ className, label, monochrome = false }: KSignalProps) {
  return (
    <span
      className={cn(
        "inline-grid size-9 shrink-0 place-items-center rounded-[11px]",
        monochrome ? "bg-current text-inherit" : "bg-primary text-primary-foreground",
        className,
      )}
      aria-hidden={label ? undefined : true}
      aria-label={label}
      role={label ? "img" : undefined}
    >
      <svg
        viewBox="0 0 32 32"
        className={cn("size-7", monochrome && "text-background")}
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <path
          d="M9 7V25M9 16L23 7M9 16L23 25"
          stroke="currentColor"
          strokeWidth="1.75"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <circle cx="9" cy="7" r="1.5" fill="currentColor" />
        <circle cx="9" cy="16" r="2" fill="currentColor" />
        <circle cx="9" cy="25" r="1.5" fill="currentColor" />
        <circle cx="23" cy="7" r="1.5" fill="currentColor" />
        <circle cx="23" cy="25" r="1.5" fill="currentColor" />
      </svg>
    </span>
  )
}
