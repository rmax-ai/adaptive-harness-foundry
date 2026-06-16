<script>
  import { base } from "$app/paths";
  const navItems = [
    { href: `${base}/`, label: "Home" },
    { href: `${base}/architecture/`, label: "Architecture" },
    { href: `${base}/demo/`, label: "Demo Results" },
  ];
</script>

<nav class="sidebar">
  <div class="brand">
    <a href={base + "/"}>Adaptive Harness Foundry</a>
    <p>Configuration-level agent harness evolution docs.</p>
  </div>

  <ul class="nav-list">
    {#each navItems as item}
      <li>
        <a href={item.href}>{item.label}</a>
      </li>
    {/each}
    <li>
      <a
        href="https://github.com/rmax-ai/adaptive-harness-foundry"
        target="_blank"
        rel="noreferrer"
      >
        GitHub Repo
      </a>
    </li>
  </ul>
</nav>

<style>
  .sidebar {
    display: grid;
    gap: 2rem;
  }

  .brand {
    display: grid;
    gap: 0.65rem;
  }

  .brand a {
    color: var(--text);
    font-size: 1.1rem;
    font-weight: 700;
    letter-spacing: 0.01em;
    text-decoration: none;
  }

  .brand p {
    color: var(--muted);
    line-height: 1.5;
    margin: 0;
  }

  .nav-list {
    display: grid;
    gap: 0.55rem;
    list-style: none;
    margin: 0;
    padding: 0;
  }

  .nav-list a {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 0.85rem;
    color: var(--text);
    display: block;
    padding: 0.85rem 1rem;
    text-decoration: none;
    transition:
      border-color 120ms ease,
      color 120ms ease,
      transform 120ms ease;
  }

  .nav-list a:hover,
  .nav-list a:focus-visible {
    border-color: var(--accent);
    color: var(--accent);
    outline: none;
    transform: translateX(2px);
  }
</style>
