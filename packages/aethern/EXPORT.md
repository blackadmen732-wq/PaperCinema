# Moving this folder into its own private repository

Nothing here refers to Paper Cinema by path: the core reads every project path from the
`aethern.json` of whatever project it runs in. So the folder can move as it is.

1. On GitHub, create a new **private** repository (for example `aethern`), with no README, licence
   or .gitignore, so it starts empty.
2. In your Paper Cinema clone, on the branch that has `packages/aethern/` (after the pull request is
   merged, that is your default branch), split the folder out with its history:
   ```
   git subtree split --prefix=packages/aethern -b aethern-export
   ```
3. Push that branch to the new repository as its `main`:
   ```
   git push git@github.com:<you>/aethern.git aethern-export:main
   ```
4. Check it: clone the new repository somewhere else and run
   ```
   python3 -m unittest discover -s tests && node --test tests/js.test.mjs
   ```
5. Optional, later: make Paper Cinema use the new repository instead of its own copy
   (`git rm -r packages/aethern`, then `git submodule add git@github.com:<you>/aethern.git packages/aethern`).
   Keep the copy until the new repository has proved itself; nothing in Paper Cinema needs to change
   either way, because it only ever imports `packages/aethern/`.
