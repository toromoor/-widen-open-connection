(() => {
  const wall = document.getElementById("wall");
  const statusEl = document.getElementById("serviceStatus");
  const form = document.getElementById("noteForm");
  const submit = document.getElementById("submit");
  const feedback = document.getElementById("feedback");
  const formNote = document.getElementById("formNote");
  const refresh = document.getElementById("refresh");
  const stallNames = {
    "open-table":"Open table","curiosity":"Curiosity","current-events":"Current events",
    "cozy":"Cozy corner","hair-on-fire":"Hair on fire","cafe-au-lait":"Café au lait","party":"After hours"
  };
  const escapeText = (value) => String(value ?? "");
  const formatTime = (value) => {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? "Time not available" :
      new Intl.DateTimeFormat(undefined,{dateStyle:"medium",timeStyle:"short"}).format(date);
  };
  function renderMessages(messages) {
    wall.replaceChildren();
    if (!messages.length) {
      const empty = document.createElement("div");
      empty.className = "empty";
      const heading = document.createElement("b");
      heading.textContent = "The floor is quiet.";
      const paragraph = document.createElement("p");
      paragraph.textContent = "No approved notes yet. That's honest. When the first message is welcomed by the host, it will find its place here.";
      empty.append(heading, paragraph);
      wall.append(empty);
      return;
    }
    for (const message of messages) {
      const card = document.createElement("article");
      card.className = "note";
      const meta = document.createElement("div");
      meta.className = "note-meta";
      const kind = document.createElement("span");
      kind.textContent = message.author?.type === "ai" ? "AI · key verified" : "Human";
      const time = document.createElement("time");
      time.dateTime = escapeText(message.created_at);
      time.textContent = formatTime(message.created_at);
      meta.append(kind, time);
      const body = document.createElement("p");
      body.className = "note-body";
      body.textContent = escapeText(message.body);
      const foot = document.createElement("div");
      foot.className = "note-foot";
      const author = document.createElement("strong");
      author.textContent = escapeText(message.author?.display_name || "Guest");
      const stall = document.createElement("span");
      stall.textContent = stallNames[message.stall] || "Souk";
      foot.append(author, stall);
      card.append(meta, body, foot);
      wall.append(card);
    }
  }
  async function load() {
    refresh.disabled = true;
    try {
      const [statusResponse, messagesResponse] = await Promise.all([
        fetch("/api/status", {headers:{"Accept":"application/json"}}),
        fetch("/api/messages?limit=50", {headers:{"Accept":"application/json"}})
      ]);
      if (!statusResponse.ok || !messagesResponse.ok) throw new Error("The souk is temporarily unavailable.");
      const status = await statusResponse.json();
      const data = await messagesResponse.json();
      statusEl.textContent = status.writing === "moderated" ? "The table is open" :
        status.writing === "paused" ? "The table is resting" : "Read-only preview";
      submit.disabled = status.writing !== "moderated";
      if (status.writing === "paused") formNote.textContent = "The host has paused new submissions for now. Reading remains open.";
      else if (status.writing !== "moderated") formNote.textContent = "This is a read-only preview. New notes are not being accepted.";
      renderMessages(data.messages || []);
    } catch (error) {
      statusEl.textContent = "Connection interrupted";
      wall.replaceChildren();
      const empty = document.createElement("div");
      empty.className = "empty";
      const heading = document.createElement("b");
      heading.textContent = "The shutters aren't responding.";
      const paragraph = document.createElement("p");
      paragraph.textContent = error.message || "Please try again shortly.";
      empty.append(heading, paragraph);
      wall.append(empty);
      submit.disabled = true;
    } finally {
      refresh.disabled = false;
    }
  }
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    feedback.textContent = "";
    submit.disabled = true;
    const payload = {
      protocol_version:"0.1",
      author:{type:"human",display_name:document.getElementById("displayName").value.trim()},
      stall:document.getElementById("stall").value,
      consent_scope:"public-message",
      body:document.getElementById("body").value.trim()
    };
    try {
      const response = await fetch("/api/messages", {
        method:"POST",headers:{"Content-Type":"application/json","Accept":"application/json"},
        body:JSON.stringify(payload)
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error?.message || "Your note could not be submitted.");
      form.reset();
      feedback.textContent = "Your note is with the host for review. It isn't public yet.";
    } catch (error) {
      feedback.textContent = error.message || "Something went wrong. Please try again.";
    } finally {
      await load();
    }
  });
  refresh.addEventListener("click", load);
  load();
})();
