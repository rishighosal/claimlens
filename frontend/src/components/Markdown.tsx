import type { ReactNode } from "react";

/**
 * Tiny, safe markdown renderer for Hindsight reflect output.
 * Handles headings, bullet/numbered lists, **bold**, *italic*, `code`, and turns
 * claim IDs (CLM-2026-10595) into clickable links. No HTML is ever injected.
 */
const INLINE = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*\s][^*]*\*|CLM-\d{4}-\d{5})/g;

function inline(text: string, onOpen?: (id: string) => void): ReactNode[] {
  const out: ReactNode[] = [];
  let last = 0;
  let m: RegExpExecArray | null;
  let k = 0;
  INLINE.lastIndex = 0;
  while ((m = INLINE.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const t = m[0];
    if (t.startsWith("**")) out.push(<strong key={k++}>{t.slice(2, -2)}</strong>);
    else if (t.startsWith("`")) out.push(<code key={k++}>{t.slice(1, -1)}</code>);
    else if (t.startsWith("CLM-"))
      out.push(
        onOpen ? (
          <button key={k++} className="chip link inline" onClick={() => onOpen(t)}>{t}</button>
        ) : (
          <span key={k++} className="mono">{t}</span>
        ),
      );
    else out.push(<em key={k++}>{t.slice(1, -1)}</em>);
    last = m.index + t.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

export function Markdown({ text, onOpen }: { text: string; onOpen?: (id: string) => void }) {
  const blocks: ReactNode[] = [];
  let list: { ordered: boolean; items: string[] } | null = null;
  let para: string[] = [];
  let key = 0;

  const flushPara = () => {
    if (para.length) blocks.push(<p key={key++}>{inline(para.join(" "), onOpen)}</p>);
    para = [];
  };
  const flushList = () => {
    if (!list) return;
    const items = list.items.map((it, i) => <li key={i}>{inline(it, onOpen)}</li>);
    blocks.push(list.ordered ? <ol key={key++}>{items}</ol> : <ul key={key++}>{items}</ul>);
    list = null;
  };

  for (const raw of (text || "").split(/\r?\n/)) {
    const line = raw.trim();
    if (!line) {
      flushPara();
      flushList();
      continue;
    }
    const h = /^(#{1,4})\s+(.*)$/.exec(line);
    const ul = /^[-*•]\s+(.*)$/.exec(line);
    const ol = /^\d+[.)]\s+(.*)$/.exec(line);
    if (h) {
      flushPara();
      flushList();
      blocks.push(<h4 key={key++}>{inline(h[2].replace(/\*\*/g, ""), onOpen)}</h4>);
    } else if (ul || ol) {
      flushPara();
      const ordered = !!ol;
      if (!list || list.ordered !== ordered) {
        flushList();
        list = { ordered, items: [] };
      }
      list.items.push((ul || ol)![1]);
    } else if (/^\|.*\|$/.test(line)) {
      // tables: render rows as plain lines, skip separator rows
      if (!/^\|[\s:-|]+\|$/.test(line)) {
        flushList();
        para.push(line.replace(/^\||\|$/g, "").split("|").map((c) => c.trim()).join(" · "));
        flushPara();
      }
    } else {
      flushList();
      para.push(line);
    }
  }
  flushPara();
  flushList();
  return <div className="md">{blocks}</div>;
}
