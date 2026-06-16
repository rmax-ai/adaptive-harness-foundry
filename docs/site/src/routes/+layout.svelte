<script>
  import Nav from "$lib/components/Nav.svelte";
</script>

<svelte:head>
  <title>Adaptive Harness Foundry Docs</title>
  <meta
    name="description"
    content="Static documentation site for Adaptive Harness Foundry."
  />
</svelte:head>

<div class="shell">
  <aside class="sidebar">
    <Nav />
  </aside>

  <main class="content">
    <slot />
  </main>
</div>

<style>
  :global(:root) {
    --bg: #0d1117;
    --bg-card: #161b22;
    --text: #c9d1d9;
    --accent: #58a6ff;
    --border: #30363d;
    --code-bg: #1a1a2e;
    --muted: #8b949e;
    --max-width: 62rem;
  }

  :global(html) {
    background:
      radial-gradient(circle at top, rgba(88, 166, 255, 0.14), transparent 28rem),
      linear-gradient(180deg, #0d1117 0%, #090c10 100%);
    color: var(--text);
    font-family:
      "IBM Plex Sans",
      "Segoe UI",
      sans-serif;
    scroll-behavior: smooth;
  }

  :global(body) {
    margin: 0;
    min-height: 100vh;
  }

  :global(*) {
    box-sizing: border-box;
  }

  :global(a) {
    color: var(--accent);
  }

  :global(p),
  :global(li) {
    line-height: 1.7;
  }

  :global(h1),
  :global(h2),
  :global(h3) {
    letter-spacing: -0.02em;
    line-height: 1.15;
  }

  :global(h1) {
    font-size: clamp(2.3rem, 4vw, 3.7rem);
    margin: 0 0 1rem;
  }

  :global(h2) {
    font-size: clamp(1.5rem, 2.5vw, 2.1rem);
    margin-top: 2.8rem;
  }

  :global(code) {
    background: var(--code-bg);
    border: 1px solid rgba(88, 166, 255, 0.12);
    border-radius: 0.45rem;
    font-family:
      "IBM Plex Mono",
      "SFMono-Regular",
      monospace;
    font-size: 0.92em;
    padding: 0.15rem 0.4rem;
  }

  :global(pre) {
    background: var(--code-bg);
    border: 1px solid var(--border);
    border-radius: 1rem;
    overflow-x: auto;
    padding: 1rem 1.15rem;
  }

  :global(pre code) {
    background: transparent;
    border: 0;
    padding: 0;
  }

  :global(ul),
  :global(ol) {
    padding-left: 1.2rem;
  }

  :global(blockquote) {
    border-left: 3px solid var(--accent);
    color: var(--muted);
    margin: 1.5rem 0;
    padding: 0.1rem 0 0.1rem 1rem;
  }

  :global(table) {
    border-collapse: collapse;
    display: block;
    max-width: 100%;
    overflow-x: auto;
  }

  :global(th),
  :global(td) {
    border: 1px solid var(--border);
    padding: 0.7rem 0.85rem;
    text-align: left;
  }

  :global(th) {
    background: rgba(255, 255, 255, 0.02);
  }

  .shell {
    display: grid;
    gap: 2rem;
    grid-template-columns: minmax(14rem, 18rem) minmax(0, 1fr);
    margin: 0 auto;
    max-width: 96rem;
    min-height: 100vh;
    padding: 1.5rem;
  }

  .sidebar {
    position: sticky;
    top: 0;
    align-self: start;
    min-height: calc(100vh - 3rem);
    padding: 1.25rem;
  }

  .content {
    background: rgba(13, 17, 23, 0.74);
    border: 1px solid var(--border);
    border-radius: 1.4rem;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.22);
    padding: clamp(1.5rem, 3vw, 3rem);
  }

  :global(.content > :first-child) {
    margin-top: 0;
  }

  :global(.content > :last-child) {
    margin-bottom: 0;
  }

  :global(.eyebrow) {
    color: var(--accent);
    font-size: 0.82rem;
    font-weight: 700;
    letter-spacing: 0.12em;
    margin-bottom: 0.8rem;
    text-transform: uppercase;
  }

  @media (max-width: 820px) {
    .shell {
      grid-template-columns: 1fr;
      padding: 1rem;
    }

    .sidebar {
      min-height: auto;
      padding: 0;
      position: static;
    }

    .content {
      padding: 1.35rem;
    }
  }
</style>
