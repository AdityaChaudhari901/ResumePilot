import { ProductMark } from "@/components/product-mark";

export default function Loading() {
  return (
    <main aria-busy="true" aria-label="Loading ResumePilot workspace" className="min-h-dvh">
      <div className="rp-frosted border-b border-border">
        <div className="mx-auto flex h-16 max-w-[90rem] items-center px-4 sm:px-6 lg:px-8">
          <ProductMark />
        </div>
      </div>
      <div className="mx-auto max-w-[90rem] px-4 py-8 sm:px-6 lg:px-8">
        <div className="h-3 w-40 animate-pulse rounded-full bg-muted" />
        <div className="mt-5 h-12 max-w-2xl animate-pulse rounded-xl bg-muted" />
        <div className="mt-4 h-5 max-w-xl animate-pulse rounded-lg bg-muted" />
        <div className="mt-10 grid gap-px overflow-hidden rounded-2xl border border-border bg-border sm:grid-cols-3 xl:grid-cols-6">
          {Array.from({ length: 6 }, (_, index) => (
            <div className="h-32 animate-pulse bg-surface-raised p-4" key={index}>
              <div className="h-3 w-8 rounded bg-muted" />
              <div className="mt-7 h-4 w-24 rounded bg-muted" />
              <div className="mt-3 h-3 w-full rounded bg-muted" />
            </div>
          ))}
        </div>
        <span className="sr-only">Loading workspace</span>
      </div>
    </main>
  );
}
