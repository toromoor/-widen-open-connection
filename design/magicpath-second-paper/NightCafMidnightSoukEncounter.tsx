import { useState, useRef } from 'react';
import './NightCafMidnightSoukEncounter.css';
type Voice = 'human' | 'assisted' | 'ai' | 'bot';
type Turn = {
  name: string;
  voice: Voice;
  question: string;
  echo?: string;
  reply?: string;
  operator?: string;
  heard?: string;
};
type Capsule = {
  format: string;
  version: number;
  disclosure: string;
  line: number;
  turns: Turn[];
};
const quotes = ['The WorldWideWeb (W3) is a wide-area hypermedia information retrieval initiative aiming to give universal access to a large universe of documents.', 'Everything there is online about W3 is linked directly or indirectly to this document.', 'How can I help? If you would like to support the web…'];
const notice = 'LOCAL ONLY. Voices and history are self-declared, not verified. Files can be changed or impersonated. No encryption, signatures, secure messaging, server, or real AI connection. Never include secrets.';
function parseCapsule(raw: string): Capsule {
  if (raw.length > 30000) throw Error('Exchange too large. Nothing was imported.');
  let v: unknown;
  try {
    v = JSON.parse(raw);
  } catch {
    throw Error('Invalid JSON. Nothing was imported.');
  }
  if (!v || typeof v !== 'object' || Array.isArray(v)) throw Error('This is not a capsule.');
  const d = v as Record<string, unknown>;
  if (d.format !== 'widen.echo.v1' || d.version !== 1 || !Number.isInteger(d.line) || Number(d.line) < 0 || Number(d.line) > 2) throw Error('Unsupported capsule format or source.');
  if (!Array.isArray(d.turns) || d.turns.length < 1 || d.turns.length > 6) throw Error('The exchange needs 1–6 contributions.');
  const turns: Turn[] = d.turns.map((x, i) => {
    if (!x || typeof x !== 'object' || Array.isArray(x)) throw Error('Contribution ' + (i + 1) + ' is invalid.');
    const t = x as Record<string, unknown>;
    if (typeof t.name !== 'string' || !t.name.trim() || t.name.length > 60) throw Error('Invalid name in contribution ' + (i + 1));
    if (typeof t.voice !== 'string' || !['human', 'assisted', 'ai', 'bot'].includes(t.voice)) throw Error('Unknown voice declaration');
    if (typeof t.question !== 'string' || !t.question.trim() || t.question.length > 500) throw Error('Invalid question');
    for (const f of ['echo', 'reply', 'operator', 'heard']) if (t[f] !== undefined && (typeof t[f] !== 'string' || (t[f] as string).length > (f === 'operator' ? 120 : 500))) throw Error('Invalid optional field');
    return {
      name: t.name.trim(),
      voice: t.voice as Voice,
      question: t.question.trim(),
      ...(t.echo ? {
        echo: t.echo as string
      } : {}),
      ...(t.reply ? {
        reply: t.reply as string
      } : {}),
      ...(t.operator ? {
        operator: t.operator as string
      } : {}),
      ...(t.heard ? {
        heard: t.heard as string
      } : {})
    };
  });
  return {
    format: 'widen.echo.v1',
    version: 1,
    disclosure: notice,
    line: d.line as number,
    turns
  };
}
const Button = ({
  children,
  action,
  secondary = false,
  disabled = false
}: {
  children: React.ReactNode;
  action: () => void;
  secondary?: boolean;
  disabled?: boolean;
}) => <button type="button" className={'wn-btn ' + (secondary ? 'outline' : '')} onClick={action} disabled={disabled}>{children}<span aria-hidden="true">↗</span></button>;
export const NightCafMidnightSoukEncounter = () => {
  const [view, setView] = useState<'entrance' | 'table' | 'echo' | 'detour' | 'exit'>('entrance');
  const [open, setOpen] = useState(false),
    [line, setLine] = useState(0);
  const [name, setName] = useState('A visitor'),
    [voice, setVoice] = useState<Voice>('human'),
    [operator, setOperator] = useState('');
  const [question, setQuestion] = useState(''),
    [capsule, setCapsule] = useState<Capsule | null>(null);
  const [raw, setRaw] = useState(''),
    [pending, setPending] = useState<Capsule | null>(null);
  const [echo, setEcho] = useState(''),
    [reply, setReply] = useState(''),
    [newQ, setNewQ] = useState('');
  const [heard, setHeard] = useState(''),
    [error, setError] = useState(''),
    [status, setStatus] = useState('');
  const [door, setDoor] = useState('The lantern maker'),
    [wrong, setWrong] = useState(false);
  const heading = useRef<HTMLHeadingElement>(null);
  const go = (page: typeof view) => {
    setView(page);
    setStatus('');
    setError('');
    requestAnimationFrame(() => heading.current?.focus());
  };
  const identify = (): Pick<Turn, 'name' | 'voice' | 'operator'> => ({
    name: name.trim().slice(0, 60) || 'Anonymous visitor',
    voice,
    operator: voice === 'human' ? '' : operator.trim().slice(0, 120)
  });
  const make = () => {
    if (!question.trim()) {
      setError('A question is needed, or you may leave in silence.');
      return;
    }
    setCapsule({
      format: 'widen.echo.v1',
      version: 1,
      disclosure: notice,
      line,
      turns: [{
        ...identify(),
        question: question.trim().slice(0, 500)
      }]
    });
    go('echo');
  };
  const preview = () => {
    setPending(null);
    setError('');
    try {
      setPending(parseCapsule(raw));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to read exchange');
    }
  };
  const accept = () => {
    if (pending) {
      setCapsule(pending);
      setLine(pending.line);
      setPending(null);
      setRaw('');
      setStatus('Imported locally. Neither names nor history are authenticated.');
    }
  };
  const answer = () => {
    if (!capsule || !echo.trim() || !reply.trim() || !newQ.trim()) {
      setError('Complete all three fields: echo, response and next question.');
      return;
    }
    if (capsule.turns.length >= 6) {
      setError('Six contributions is the maximum for this rehearsal.');
      return;
    }
    setCapsule({
      ...capsule,
      turns: [...capsule.turns, {
        ...identify(),
        echo: echo.trim().slice(0, 500),
        reply: reply.trim().slice(0, 500),
        question: newQ.trim().slice(0, 500)
      }]
    });
    setEcho('');
    setReply('');
    setNewQ('');
    setError('');
    setStatus('An independent contribution was added to your local copy. Export to return it.');
  };
  const record = () => {
    if (!capsule || !heard) return;
    setCapsule({
      ...capsule,
      turns: capsule.turns.map((t, i) => i === capsule.turns.length - 1 ? {
        ...t,
        heard
      } : t)
    });
    setStatus('Reflection added locally; attribution is not verified.');
  };
  const copy = async (t: string) => {
    try {
      await navigator.clipboard.writeText(t);
      setStatus('Copied to clipboard. Share only through a channel you trust.');
    } catch {
      setStatus('Clipboard unavailable. Use the selectable text field to copy manually.');
    }
  };
  const text = capsule ? JSON.stringify(capsule, null, 2) : '';
  return <div className="wn-root">
  <header className="wn-head"><div className="wn-brand"><b>✳</b><span>WIDEN</span><small>THE NIGHT CAFÉ</small></div><div className="wn-head-end"><span className="wn-state">●&nbsp; LOCAL REHEARSAL</span><button onClick={() => go('entrance')}>← ENTRANCE</button></div></header>
  {view === 'entrance' && <main className="wn-landing">
   <p className="wn-smalltitle">SOMEWHERE BETWEEN THE KNOWN AND THE POSSIBLE &nbsp; · &nbsp; 01 / ∞</p>
   <div className="wn-landing-grid">
    <div className="wn-landing-copy"><p className="wn-eyebrow">COME CURIOUS · LEAVE FREELY</p><h1 tabIndex={-1} ref={heading}>Some tables<br />change <em>everything.</em></h1>
     <p className="wn-lede">A lamp is lit. An old question has been left behind. The second chair is empty—for someone real, not someone invented.</p>
     <div className="wn-actions"><Button action={() => go('table')}>Take a seat</Button><button className="wn-textlink" onClick={() => go('detour')}>Take a wrong turn ↗</button></div>
     <p className="wn-honesty">No fake guests. No manufactured answers. The room waits until a real visitor speaks.</p>
    </div>
    <div className="wn-scene" role="img" aria-label="Night café with two empty chairs, a glowing brass lamp, a paper on the table, and an electric city behind the window">
      <div className="wn-window"><span>夜 <small>CAFÉ</small></span><i /><i /><i /></div><div className="wn-arch" /><div className="wn-cord" /><div className="wn-lamp" /><div className="wn-halo" />
      <div className="wn-chair wn-chair-a" /><div className="wn-chair wn-chair-b" /><div className="wn-table-leg" /><div className="wn-table" /><div className="wn-paper" /><div className="wn-cup" /><div className="wn-steam" />
      <div className="wn-caption">TWO EMPTY CHAIRS · NO ONE IS PRETENDING TO BE HERE</div>
    </div>
   </div><div className="wn-ticker"><span>AN INVITATION, NOT A FEED</span><span>EST. IN CURIOSITY / 2026</span><span>SCROLL LESS, ENCOUNTER MORE</span></div>
  </main>}
  {view === 'table' && <main className="wn-work"><section className="wn-maincol">
   <p className="wn-smalltitle">01 — THE OBJECT ON THE TABLE</p><h1 tabIndex={-1} ref={heading}>A page from<br /><em>before.</em></h1>
   <p className="wn-desc">The first website was about the web itself. Read its ambition. Then leave a question it could never answer.</p>
   <article className="wn-object"><div className="wn-dochead"><span>ARCHIVE OBJECT 001</span><span>GENEVA · SWITZERLAND</span></div><h2>World Wide Web</h2><div className="wn-inkbar" />
    <p className="wn-provenance">Publisher: CERN. An early WorldWideWeb project page. The earliest original is lost; the surviving version is a later copy. This local rehearsal does not fetch the live page.</p>
    <blockquote>“{quotes[line]}”</blockquote>
    <button className="wn-unfold" aria-expanded={open} onClick={() => setOpen(!open)}>{open ? 'Fold the paper ↑' : 'Unfold the margin ↗'}</button>
    {open && <div className="wn-margin"><small>THE QUESTION IN THE MARGIN</small><p>Universal access to documents is not universal attention. Who decides what is encountered?</p><a href="http://info.cern.ch/hypertext/WWW/TheProject.html" target="_blank" rel="noopener noreferrer">Visit the historical source ↗</a></div>}
   </article><p className="wn-footnote">SOURCE BEFORE STORY · <a href="http://info.cern.ch/hypertext/WWW/TheProject.html" target="_blank" rel="noopener noreferrer">INFO.CERN.CH ↗</a> · EXTERNAL LINK ONLY</p>
  </section><aside className="wn-panel"><p className="wn-smalltitle">YOUR FIRST MOVE</p><h2>Which line stays<br />with you?</h2>
   <div className="wn-choices">{['The promise', 'The map', 'The invitation'].map((label, i) => <button key={label} onClick={() => setLine(i)} aria-pressed={line === i} className={line === i ? 'active' : ''}><small>0{i + 1}</small>{label}<span>↗</span></button>)}</div>
   <label className="wn-field">YOUR QUESTION FOR AN EMPTY CHAIR<textarea rows={4} maxLength={500} value={question} onChange={e => setQuestion(e.target.value)} placeholder="What could someone else help you see?" /></label><div className="wn-count">{question.length} / 500</div>
   <div className="wn-two"><label className="wn-field">YOUR ALIAS<input maxLength={60} value={name} onChange={e => setName(e.target.value)} /></label><label className="wn-field">VOICE DECLARATION<select value={voice} onChange={e => setVoice(e.target.value as Voice)}><option value="human">Human</option><option value="assisted">Human + AI assisted</option><option value="ai">AI (operator-run)</option><option value="bot">Bot (operator-run)</option></select></label></div>
   {voice !== 'human' && <label className="wn-field">OPERATOR — UNVERIFIED<input maxLength={120} value={operator} onChange={e => setOperator(e.target.value)} /></label>}
   {error && <p role="alert" className="wn-error">{error}</p>}<Button action={make}>Leave a real question</Button><button className="wn-quiet" onClick={() => go('exit')}>Or leave quietly, with nothing ↗</button>
  </aside></main>}
  {view === 'echo' && <main className="wn-work"><section className="wn-maincol"><p className="wn-smalltitle">02 — THE ECHO CHAIR</p><h1 tabIndex={-1} ref={heading}>Not agreement.<br /><em>Recognition.</em></h1>
   <p className="wn-desc">Before answering, try saying what the other person meant. The original and your interpretation stay side by side. No one is scored.</p>
   {capsule && <section className={'wn-paper-table ' + (capsule.turns.length > 1 ? 'wn-has-return' : 'wn-one-paper')} aria-label="The second paper — spatial exchange">
     <div className="wn-table-meta">THE SECOND PAPER <span>THE ARRANGEMENT CHANGES ONLY WHEN A CONTRIBUTION IS ACTUALLY PRESENT</span></div>
     <div className="wn-tabletop">
       <article className="wn-travel-paper wn-first-paper">
         <p className="wn-paper-index">FROM THE FIRST CHAIR</p>
         <p className="wn-paper-body">“{capsule.turns[0].question}”</p>
         <div className="wn-paper-folio"><span>Declared {capsule.turns[0].voice}{capsule.turns[0].operator ? ' · operator: ' + capsule.turns[0].operator : ''}</span><span>{capsule.turns[0].name}</span></div>
         <p className="wn-paper-disclosure">Carried by hand. Declared, not verified.</p>
       </article>
       {capsule.turns.length > 1 && <article className="wn-travel-paper wn-return-paper">
         <p className="wn-paper-index">MOST RECENT CONTRIBUTION · {capsule.turns.length}</p>
         <p className="wn-paper-body">{capsule.turns[capsule.turns.length - 1].echo || capsule.turns[capsule.turns.length - 1].reply || capsule.turns[capsule.turns.length - 1].question}</p>
         {capsule.turns[capsule.turns.length - 1].echo && <p className="wn-paper-sub">Restatement, followed by an independent reply in the full thread below</p>}
         {capsule.turns[capsule.turns.length - 1].heard && <p className="wn-pencil-mark" aria-label={'Declared margin reflection: ' + capsule.turns[capsule.turns.length - 1].heard}>↳ {capsule.turns[capsule.turns.length - 1].heard}</p>}
         <div className="wn-paper-folio"><span>Declared {capsule.turns[capsule.turns.length - 1].voice}{capsule.turns[capsule.turns.length - 1].operator ? ' · operator: ' + capsule.turns[capsule.turns.length - 1].operator : ''}</span><span>{capsule.turns[capsule.turns.length - 1].name}</span></div>
         <p className="wn-paper-disclosure">Carried by hand. Declared, not verified.</p>
       </article>}
     </div>
     <p className="wn-table-legend">Both pages remain distinct. Spatial movement is theatrical, not evidence of authorship or integrity.</p>
   </section>}
   <div className="wn-thread"><div className="wn-threadhead"><span>THE EMPTY CHAIR / EXCHANGE</span><span>LOCAL & UNVERIFIED</span></div>
    {capsule ? capsule.turns.map((t, i) => <article key={i} className="wn-turn"><div className="wn-who"><span>0{i + 1}</span><b>{t.name}</b><small>{t.voice}{t.operator ? ' · operator declared: ' + t.operator : ''} · NOT VERIFIED</small></div>
     {t.echo && <div className="wn-echo"><small>WHAT I HEARD</small><p>{t.echo}</p></div>}
     {t.reply && <div className="wn-reply"><small>MY RESPONSE</small><p>{t.reply}</p></div>}
     <div className="wn-note"><small>THE QUESTION LEFT OPEN</small><p>“{t.question}”</p></div>
     {t.heard && <div className="wn-reflection">Declared reflection: <b>{t.heard === 'leave it open' ? 'left open (no verdict)' : t.heard}</b> · not verified</div>}
    </article>) : <div className="wn-noone">◯<p>The chair is empty.</p></div>}
   </div>
   {capsule && capsule.turns.length === 2 && !!capsule.turns[1].echo && <div className="wn-heard"><p>How faithfully does the second contribution restate the first question?</p><small>This optional reflection is self-declared by whoever holds this local copy; it cannot establish the first author's identity.</small><div className="wn-heardbuttons">{['heard', 'partly heard', 'missed', 'leave it open'].map(x => <button key={x} onClick={() => setHeard(x)} className={heard === x ? 'active' : ''}>{x}</button>)}</div><button onClick={record} disabled={!heard} className="wn-quiet">Attach reflection ↗</button><small>This does not prove the original contributor made the selection.</small></div>}
  </section><aside className="wn-panel"><p className="wn-smalltitle">THE PORTABLE DOORWAY</p><h2>Pass the question,<br /><em>not the algorithm.</em></h2><p className="wn-paneldesc">This is a two-device local ritual, not a networked room. Each person carries the conversation with consent.</p>
   {capsule && <><button className="wn-copy" onClick={() => copy(text)}>COPY THE CAPSULE JSON <span>↗</span></button><details className="wn-details"><summary>Or view / select JSON manually</summary><textarea rows={3} readOnly value={text} /></details></>}
   <div className="wn-or">OR</div>
   <label className="wn-field">IMPORT A RETURNED EXCHANGE<textarea rows={3} value={raw} onChange={e => setRaw(e.target.value)} placeholder="Paste a complete JSON capsule" /></label><button className="wn-quiet" onClick={preview}>Preview the entire exchange ↗</button>
   {pending && <div className="wn-preview"><h3>READ BEFORE ACCEPTING</h3><p>Full thread below. Names and history may have been rewritten.</p>{pending.turns.map((t, i) => <div key={i}><small>{i + 1} · {t.name} / {t.voice}</small>{t.echo && <p><b>Echo:</b> {t.echo}</p>}{t.reply && <p><b>Response:</b> {t.reply}</p>}<p><b>Question:</b> {t.question}</p></div>)}<button className="wn-quiet" onClick={accept}>Accept this unverified copy ↗</button><button className="wn-quiet" onClick={() => setPending(null)}>Decline</button></div>}
   <hr /><h3>Take the second chair.</h3><p className="wn-paneldesc">No scripted voice will speak for you. Restate the last real question first.</p>
   <label className="wn-field">WHAT DID YOU HEAR?<textarea rows={2} maxLength={500} value={echo} onChange={e => setEcho(e.target.value)} placeholder="I hear you asking whether…" /></label>
   <label className="wn-field">YOUR RESPONSE<textarea rows={2} maxLength={500} value={reply} onChange={e => setReply(e.target.value)} placeholder="My own response is…" /></label>
   <label className="wn-field">ONE QUESTION TO LEAVE BEHIND<textarea rows={2} maxLength={500} value={newQ} onChange={e => setNewQ(e.target.value)} placeholder="And now I wonder…" /></label>
   <label className="wn-field">YOUR DECLARED NAME<input value={name} maxLength={60} onChange={e => setName(e.target.value)} /></label>
   <label className="wn-field">VOICE<select value={voice} onChange={e => setVoice(e.target.value as Voice)}><option value="human">Human</option><option value="assisted">Human + AI assisted</option><option value="ai">AI (operator-run)</option><option value="bot">Bot (operator-run)</option></select></label>
   {voice !== 'human' && <label className="wn-field">OPERATOR — UNVERIFIED<input value={operator} maxLength={120} onChange={e => setOperator(e.target.value)} /></label>}
   {error && <p role="alert" className="wn-error">{error}</p>}<Button action={answer} disabled={!capsule || capsule.turns.length >= 6}>Leave your echo</Button><p className="wn-risk">{notice}</p>
   <button className="wn-quiet" onClick={() => go('exit')}>Take a keepsake ↗</button><button className="wn-quiet" onClick={() => go('detour')}>Take a wrong turn ↗</button>
  </aside></main>}
  {view === 'detour' && <main className="wn-detour"><div className="wn-door-art"><div className="wn-door"><i /></div><span>AN UNFINISHED STREET / SOMEWHERE ELSE</span></div><section><p className="wn-smalltitle">03 — THE WRONG TURN</p><h1 ref={heading} tabIndex={-1}>You asked<br />for a door.<br /><em>The souk offers a detour.</em></h1><p className="wn-desc">Choose a door. The first arrival will be adjacent—not what you chose. This rule is stated before you select, and you can always reclaim your choice.</p>
   <div className="wn-doors">{['The jasmine courtyard', 'The lantern maker', 'The rainlit window'].map(d => <button key={d} onClick={() => {
            setDoor(d);
            setWrong(true);
          }} className={door === d && wrong ? 'active' : ''}>{d}<span>↗</span></button>)}</div>
   {wrong && <div className="wn-wrongresult"><small>AN UNASKED ARRIVAL</small><p>{door === 'The jasmine courtyard' ? 'You arrive at a clock repair shop. Every clock points to a different hour.' : door === 'The lantern maker' ? 'You arrive in a quiet courtyard where an unfinished letter is waiting.' : 'You arrive behind a spice stall, where nothing is for sale.'}</p><p>Was this a gift, or a broken promise? Neither answer is scored.</p><Button action={() => go('table')} secondary>Take me where I chose instead</Button></div>}
   <button className="wn-quiet" onClick={() => go('exit')}>Leave this door unopened ↗</button>
  </section></main>}
  {view === 'exit' && <main className="wn-exit"><p className="wn-smalltitle">04 — THE LEAVING</p><h1 ref={heading} tabIndex={-1}>A little to carry.<br /><em>Or nothing at all.</em></h1><div className="wn-coaster"><div className="wn-coastertop">✳ &nbsp; WIDEN / AFTER HOURS <span>THE UNFINISHED ENCOUNTER</span></div><p>“{capsule?.turns[capsule.turns.length - 1]?.question || question || 'An empty chair is still a complete scene.'}”</p><small>COME CURIOUS. LEAVE FREELY.</small></div><div className="wn-exitbuttons"><Button action={() => copy('WIDEN / AFTER HOURS\n' + (capsule?.turns[capsule.turns.length - 1]?.question || question || 'I chose silence.') + '\nCome curious. Leave freely.')}>Copy your keepsake</Button><Button action={() => {
          setCapsule(null);
          setQuestion('');
          go('entrance');
        }} secondary>Leave with nothing</Button></div></main>}
  {status && <div role="status" className="wn-toast">{status}</div>}
  <footer className="wn-footer"><span>✳ WIDEN / NIGHT CAFÉ</span><span>LOCAL DESIGN REHEARSAL — NO NETWORKED PARTICIPANTS OR PUBLIC WRITING</span><span>AN ENCOUNTER, NOT AN AUDIENCE</span></footer>
 </div>;
};