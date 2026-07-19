export function BrandMark({ size = 34 }: { size?: number }) {
  return <svg className="brand-logo-mark" width={size} height={size} viewBox="0 0 64 64" role="img" aria-label="Veridex logo"><path d="M9 9h14l9 18 5-12c2-4 5-6 9-6h9L44 31l7 15h-9c-4 0-7-2-9-6l-4-8-5 12c-2 4-5 6-9 6H9l10-23L9 9Z" fill="#65c2b2"/><path d="M18 35h15l5-16c1-4 4-6 8-6h8l-9 22h-8l-4 14c-1 4-4 6-8 6h-9l9-20H18Z" fill="#367eaa"/><path d="M36 31h10l5 8h7c3 0 5 2 5 5s-2 5-5 5h-9c-4 0-7-2-9-6l-4-7Z" fill="#3476a2"/></svg>;
}
