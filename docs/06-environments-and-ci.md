# 6. Two environments, and what each is allowed to do

[The strategy](03-test-strategy.md) says where each check belongs. This
document says *where it runs*, which turned out to be the harder question: the
application under test is a public demo used by other people, and a suite that
treats somebody else's running instance as its own is either dishonest about
what it covers or rude to whoever is using it at the time.

So there are two environments, and each one is allowed a different set of
actions.

## Why two

The hosted storefront at
[practicesoftwaretesting.com](https://practicesoftwaretesting.com) is the real
article: the deployment everyone else practises against, on infrastructure
nobody here controls. It is the honest target for "does the application still
work" — and it is the wrong place to prove that an order can be placed,
because every proof leaves a real order in a shared database.

The stand is the same application, started from the upstream project's own
images by `scripts/stand-up.sh`, seeded from scratch, and thrown away at the
end of the run. It is ours, so it can be written to.

Neither environment alone is enough. The hosted site is the only one that
says anything about the deployment people actually use; the stand is the only
one where the write paths — the contact form reaching the backend, a guest
checkout that ends in a real order — can be exercised rather than simulated.

## What each one allows

| | Hosted site | Our stand |
| --- | --- | --- |
| Whose it is | somebody else's | ours, and disposable |
| `BASE_URL` | `https://practicesoftwaretesting.com` | `http://localhost:4200` |
| `API_BASE_URL` | `https://api.practicesoftwaretesting.com` | `http://localhost:8091` |
| Writes | intercepted (`MOCK_CONTACT_API=true`) | sent for real (`MOCK_CONTACT_API=false`) |
| Order placement | deselected by default (`creates_data`) | run, like everything else (`-m ""`) |
| Timeouts | 30 s: a shared host over the internet | 10 s: a local stand that answers in milliseconds, so a longer wait would only hide a hang |
| Data | generated per run, so two runs never collide | seeded fresh before the run |

On the hosted site a POST is answered in the browser and the payload is
asserted instead of being delivered. That is not only politeness: asserting
the request body catches the bug class where a field is renamed or dropped on
the way out, which a "200 OK" from the server would not. The same fixture
records the payload in both modes, so the assertions do not change when the
suite moves to the stand — only whether the request is allowed through.

## Why the stand's images are pinned by digest

`docker-compose.stand.yml` names every image by `@sha256:…`, not by a tag.

A showcase that goes red because somebody else published a release is a
showcase nobody trusts. Tags move; the published page and the README quote
numbers from a run and must stay reproducible; and a failure has to mean
something about this repository, not about what upstream shipped this morning.
Pinning turns "the suite broke" into "somebody changed the pin", which is a
commit with a diff and a reason.

One image is not upstream's: upstream publishes its `web` image for arm64
only, so the stand serves the same application through official multi-arch
nginx with upstream's own vhost (`stand/vhost.conf`). That is a deliberate
substitution, recorded in the compose file next to the image it replaces.

## Why the production run stopped being a gate

The hosted storefront answers **HTTP 403** to data-centre IP ranges, which
includes every GitHub-hosted runner. Nothing is broken when that happens: the
environment simply cannot be reached from there.

A gate has to be able to fail for a reason the author can act on. A job that
goes red because GitHub's address range is blocked fails for a reason nobody
in this repository can fix, and after the second occurrence its red stops
being read at all. So the gate moved to the environment where a failure is
always about the code:

- **Every pull request, and every push to `main`,** runs the whole suite
  against the stand, writes included. That run is the gate, and on `main` it
  is also what publishes the showcase page — which is generated from the
  results of the run that had to pass first.
- **Nightly, and on demand**, the same workflow probes the hosted site, runs
  the API suite against it, and runs the browser suite only if the probe
  answered 200. That run is a watch, not a gate: it is how a change in the
  hosted deployment gets noticed, and it blocks nothing.

The reachability probe was kept precisely because it turns an unreachable
environment into a skip with an explanation rather than into a wall of red.

## When the nightly run reports a skip

Read it as *"the hosted site could not be reached from this runner"*, and
nothing more:

- it says nothing about the product — no assertion ran;
- it says nothing about the suite — the same tests pass against the stand in
  the gate run and locally against the hosted site, where the address is not
  blocked;
- it is not a result to be waived, because it is not a result at all. The
  probe job writes the reason into the run's annotations, with the status code
  it got.

What would deserve attention is the opposite: the probe answering 200 and the
browser suite then failing. That is the hosted deployment disagreeing with the
stand, which is the one thing this nightly run exists to find.

Locally the hosted site is reachable, so the browser suite is run there
(`make ui`, `make e2e`). In a project with a budget, a self-hosted runner on
an address the site accepts would close the gap; for a portfolio project, a
skip that explains itself is the honest end of the road.
