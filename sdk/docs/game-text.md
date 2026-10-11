# The game's own names and texts (hd2.text)

HD2Runtime 0.31.2. **Offline only: not live-tested.** The tests cover the lookup on the offline text registry and the
generated name records against the research; no game session has shown these names yet.

The Runtime's catalogues name every object by an English key (`AR-23 Liberator`). The game has the same names in all
15 of its languages. `hd2.text` reads them from the game, in the language the game is set to, so a tool or a mod can
show `AR-23 解放者` to a player who plays in Chinese:

```lua
local hd2 = require('mods/skyeshade/hd2runtime')
local overlay = hd2.ui.overlay()
overlay:draw(function(d)
    -- Ask when drawing: the game may not have registered its text when the mod loads.
    local name = hd2.text.name('weapon', 'AR-23 Liberator') or 'AR-23 Liberator'
    d:text(name, 40, 40)
end)
```

- **Read-only.** Nothing is written, nothing needs an acknowledgement, and nothing raises on game state: a lookup that
  cannot answer returns `nil` (or `false`), a code and a reason. Show your own text then (the key).
- **The key stays the identity.** Search, save and export by the key; show the name.
- **Only the game's current language.** The game keeps one language's texts in memory and swaps them when the player
  changes language. Another language cannot be read (`LANGUAGE_NOT_LOADED`), and the Runtime ships no copy of the
  game's texts. The game's language is not `hd2.ui.language()`, the language HD2Runtime's own panels use (the F10
  Language setting can force another one).
- **Drawing.** Overlays draw CJK, Cyrillic and the other scripts through the game's language fonts
  (`docs/ui-overlay.md`); `hd2.ui.can_draw(text)` says whether a text can be drawn now.

## API

| Call | Returns |
|---|---|
| `hd2.text.language()` | the game's language code (`'us'`, `'de'`, `'cn'` ...), or `nil, code, reason` |
| `hd2.text.available()` | `true, language`, or `false, code, reason` |
| `hd2.text.name(kind, key)` | `name, parts`, or `nil, code, reason` |
| `target:display_name()` | the same, for a target (`hd2.weapon(key):display_name()`) |
| `hd2.text.game(id[, opts])` | `text, language`, or `nil, code, reason` |

- `kind` is `'weapon'` (primary and secondary weapons), `'support_weapon'`, `'throwable'`, `'backpack'`,
  `'vehicle'`, `'booster'` or `'stratagem'`; `key` is the name `hd2.<kind>(key)` takes. `display_name()` exists on
  the targets of those builders, and on an underbarrel (`weapon:underbarrel()`), which has no game name (`NO_NAME`).
- `parts` is `{prefix, name, name_upper, description, language}`: the designation (`'AR-23'`), the name, the upper-case
  name, the game's description with its colour markup stripped, and the language code.
- `hd2.text.game(id)` reads one text by its id (a u32, or 8 hex digits with or without `0x`). Ids are internal to the
  Runtime's catalogues (they are not published); this is for texts a mod already knows the id of. `opts` is a language
  code you expect (`LANGUAGE_NOT_LOADED` unless it is the current one) or `{language = code, plain = true}`; `plain`
  strips the `<c=#RRGGBB>...</c>` colour markup some texts carry.

### Codes

| Code | Meaning |
|---|---|
| `UNAVAILABLE` | the game has not registered its texts yet (early start-up), or is switching language: ask again later |
| `UNSUPPORTED_BUILD` | the game build is not the one the text research covers: show the keys |
| `LANGUAGE_NOT_LOADED` | a language other than the game's current one was asked for |
| `UNSUPPORTED_LANGUAGE` | not one of the game's 15 language codes |
| `NO_TEXT` | no game table holds the text in this language, or it is empty |
| `INVALID_TEXT` | longer than 4096 bytes, or not UTF-8 (never seen; the text is refused, not cut) |
| `UNKNOWN_OBJECT` | no reviewed object of that kind has that key |
| `NO_NAME` | the object has no game name: the three underbarrels |

## How a name is composed

`<designation> <name>`, as the armory shows it (`AR-23 Liberator`):

1. The designation is the game's prefix text of the object. Where it is empty in a language (the SG-88's in every
   language but English) the English designation stands in: designations are model numbers. Stratagems have no
   designation member in the game's data, and the support-weapon backpacks' records have none (`Autocannon Backpack`):
   for them the designation of the Runtime's key stands in (`A/MG-43 Machine Gun Sentry`, `AC-8 Autocannon Backpack`).
2. The name is the game's cased name, or its upper-case one where the object has no cased text (the CQC melee weapons,
   LAS-58 Talon, TED-63 Dynamite, LIFT-860 Hover Pack, Dead Sprint: the same in every language).
3. One space joins them; surrounding spaces are trimmed. A name that already begins with its designation
   (`LAS-13 Trident`) is not given it twice.

**Where the game's name differs from the key.** The game's name is shown; the key does not change:

| Key | The game's name |
|---|---|
| `CQC-73 Entrenchment Tool` | CQC-72 Entrenchment Tool (the support weapon's key is `CQC-72 Entrenchment Tool`) |
| `RL-77 Airburst Rocket Launcher Backpack` | Airburst Rocket Backpack |
| `FRV (Super Earth variant)` | M-102 GUNNER FRV (its own record carries the M-102's names) |
| `GATER Oil Rig` | GROUND ALL-TERRAIN EXTRACTION RIG |

Case and punctuation can also differ from the key (`P-35 Re-educator`, `TD-220 Bastion Mk XVI`).

## Where the names come from

- Weapons, throwables, backpacks and vehicles: the game's encyclopedia record of the object's entity resource, the
  record the armory and the HUD read. A support weapon is named by the weapon it delivers.
- Boosters: the game's booster table row of each booster.
- Stratagems: the stratagem's own row (the record the stratagem menus read).

The generators (`scripts/game_names.py`) stamp each object's text ids into the runtime catalogues by identity (entity
resource, booster value, stratagem id), never by name. The lookup is the game's own: the first registered text table
holding the id in the current language wins. A text is copied out with a bounded read, checked as UTF-8 and cached
until the game re-registers its texts (a language change), so a language change shows the new names on the next
lookup. Private research: `research/docs/game-text-api-F5FEE03DCFDB.md`.

## Limits

- Not live-tested. Suggested check: switch the game to Chinese aboard the ship and look at the names; switch back;
  start a mission and look again.
- Mounted weapons, sentries and enemies have no `display_name` yet (their records name the gun or the unit, not the
  Runtime's key).
- A game update can change text ids; the names then show `NO_TEXT` or `UNSUPPORTED_BUILD` until the catalogues are
  regenerated, and you show the keys.
