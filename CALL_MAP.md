# App Call Map

## 1 — Startup Flow

```mermaid
flowchart TD
    WA["work_app.py\nmain()"]
    M["tui_log/__main__.py\nmain()"]
    PA["_parse_args()"]
    CFG["AppConfig.load()"]
    DCP["_default_config_path()"]
    TR["TagRegistry.from_config()"]
    IDB["init_db() → migrate()"]
    GC["get_connection()"]
    PUC["project_upsert_from_config()"]
    RUN["flet_app.main.run()"]
    WApp["WorkApp.__init__()"]
    SP["WorkApp.setup_page()"]
    KB["keybindings.attach()"]
    CLK["WorkApp._start_clock()"]
    WAL["_wal_cleanup()"]

    WA --> M
    M --> PA
    M --> CFG
    CFG --> DCP
    CFG --> TR
    M --> IDB
    IDB --> GC
    M --> PUC
    M --> RUN
    RUN --> WApp
    RUN --> SP
    SP --> KB
    SP --> CLK
    M --> WAL
```

---

## 2 — WorkApp Initialization

```mermaid
flowchart TD
    WApp["WorkApp.__init__()"]
    AS["AppState()"]
    LA["state.load_all()"]
    LL["state.load_log()"]
    LT["state.load_todos()"]
    LCO["state.load_carry_over()"]
    CAS["state.check_active_session()"]
    LP["LogPanel()"]
    CP["ContentPanel()"]
    TP["TodoPanel()"]
    OC["state.on_change = _refresh_all_panels"]

    WApp --> AS
    WApp --> LA
    LA --> LL
    LA --> LT
    LA --> LCO
    LA --> CAS
    WApp --> LP
    WApp --> CP
    WApp --> TP
    WApp --> OC
```

---

## 3 — Keybinding Dispatch

```mermaid
flowchart LR
    KB["keybindings._dispatch(e, app)"]

    KB -->|Space / N| FOC["action_focus_log_input()"]
    KB -->|F| SF["action_start_focus()"]
    KB -->|A| AT["action_add_todo()"]
    KB -->|M| TC["action_toggle_content()"]
    KB -->|T| TT["action_toggle_todos()"]
    KB -->|W| WR["action_open_weekly()"]
    KB -->|V| VL["action_view_latest()"]
    KB -->|E| EE["action_edit_entry()"]
    KB -->|C| CT["action_change_tag()"]
    KB -->|B| PF["action_prev_filter()"]
    KB -->|N after filter| NF["action_next_filter()"]
    KB -->|Shift+D| DE["action_delete_entry()"]
    KB -->|D| TD["action_todo_done()"]
    KB -->|X| TX["action_todo_delete()"]
    KB -->|Enter| TA["action_todo_activate()"]
    KB -->|R| RA["action_refresh_all()"]
    KB -->|Q| QQ["action_quit()"]
    KB -->|↑ K| AU["action_arrow(up)"]
    KB -->|↓ J| AD["action_arrow(down)"]
    KB -->|Tab| CYC["action_cycle_panel()"]
    KB -->|I| TDL["action_todo_detail()"]
```

---

## 4 — Core Action Flows

```mermaid
flowchart TD
    subgraph LOG ["Log Actions"]
        OLS["_on_log_submit()"]
        OLS --> db_la["db.log_add()"]
        OLS --> sll["state.load_log()"]
        OLS --> rap["_refresh_all_panels()"]

        EE["action_edit_entry()"]
        EE --> db_lg["db.log_get()"]
        EE --> sce["show_content_edit()"]
        sce -->|on_save| db_lu["db.log_update()"]
        db_lu --> sll2["state.load_log()"]
        sll2 --> rap2["_refresh_all_panels()"]

        CT["action_change_tag()"]
        CT --> db_lg2["db.log_get()"]
        CT --> sts["show_tag_select()"]
        sts -->|on_select| db_lu2["db.log_update()"]
        db_lu2 --> sll3["state.load_log()"]
        sll3 --> rap3["_refresh_all_panels()"]

        DE["action_delete_entry()"]
        DE --> scf["show_confirm()"]
        scf -->|confirmed| db_ld["db.log_delete()"]
        db_ld --> sll4["state.load_log()"]
        sll4 --> rap4["_refresh_all_panels()"]
    end
```

```mermaid
flowchart TD
    subgraph TODO ["Todo Actions"]
        AT["action_add_todo()"]
        AT --> snt["show_new_todo()"]
        snt -->|on_save| db_ta["db.todo_add()"]
        db_ta --> ltd["state.load_todos()"]
        ltd --> rap["_refresh_all_panels()"]

        TA["action_todo_activate()"]
        TA --> db_ts["db.todo_set_status()"]
        db_ts --> ltd2["state.load_todos()"]
        ltd2 --> rtp["todo_panel.render()"]

        TD["action_todo_done()"]
        TD -->|if session| db_se["db.session_end()"]
        TD --> db_ts2["db.todo_set_status(done)"]
        TD --> db_la["db.log_add(done)"]
        TD --> ltd3["state.load_todos()"]
        ltd3 --> rap2["_refresh_all_panels()"]

        TX["action_todo_delete()"]
        TX --> scf["show_confirm()"]
        scf -->|confirmed| db_ts3["db.todo_set_status(cancelled)"]
        db_ts3 --> ltd4["state.load_todos()"]
        ltd4 --> rtp2["todo_panel.render()"]

        TDL["action_todo_detail()"]
        TDL --> std["show_todo_detail()"]
        std -->|on_close| ltd5["state.load_todos()"]
        ltd5 --> rap3["_refresh_all_panels()"]
    end
```

---

## 5 — Focus Session Lifecycle

```mermaid
flowchart TD
    SF["action_start_focus()"]
    SF --> sga["db.session_get_active()"]
    sga -->|existing?| se["db.session_end(previous)"]
    SF --> ss["db.session_start()"]
    SF --> cac["state.check_active_session()"]
    SF --> rap["_refresh_all_panels()"]
    SF --> sfoc["show_focus(dialog)"]

    sfoc -->|minimize| CLK["_start_clock() ticks timer\ntodo_panel.update_session_timer()"]
    sfoc -->|F key again| FS["_finalize_session()"]

    FS --> sdb["show_debriefing(dialog)"]
    sdb -->|on_debrief| db_se["db.session_end()"]
    db_se --> db_la["db.log_add()"]
    db_la --> db_na["db.note_add()"]
    db_na --> cac2["state.check_active_session()"]
    cac2 --> lall["state.load_all()"]
    lall --> rap2["_refresh_all_panels()"]
```

---

## 6 — State & Panel Render Chain

```mermaid
flowchart LR
    ANY["Any DB mutation\n(action_*)"]
    LA["state.load_all()\nor load_log()/load_todos()"]
    ONC["state.on_change()\n= _refresh_all_panels()"]
    LPR["log_panel.render()"]
    TPR["todo_panel.render()"]
    SDE["_show_displayed_entry()"]
    CP["content_panel.show_entry()"]

    ANY --> LA
    LA --> ONC
    ONC --> LPR
    ONC --> TPR
    ONC --> SDE
    SDE --> CP
```

---

## 7 — Database Layer

```mermaid
flowchart TD
    GC["schema.get_connection(db_path)"]

    subgraph LOG_DB ["log_entries"]
        la["log_add()"] --> GC
        lg["log_get()"] --> GC
        lu["log_update()"] --> GC
        ld["log_delete()"] --> GC
        lgd["log_get_day()"] --> GC
        lga["log_get_all()"] --> GC
        lob["log_get_open_blocks()"] --> GC
        lut["log_used_tags()"] --> GC
    end

    subgraph TODO_DB ["todos"]
        ta["todo_add()"] --> GC
        tg["todo_get()"] --> GC
        tl["todo_list()"] --> GC
        tss["todo_set_status()"] --> GC
        tu["todo_update()"] --> GC
        tdl["todo_delete()"] --> GC
    end

    subgraph SESSION_DB ["focus_sessions"]
        sst["session_start()"] --> GC
        sen["session_end()"] --> GC
        sga["session_get_active()"] --> GC
        slt["session_total_today()"] --> GC
    end

    subgraph NOTE_DB ["todo_notes"]
        na["note_add()"] --> GC
        nlft["note_list_for_todo()"] --> GC
        nlfs["note_list_for_session()"] --> GC
    end

    subgraph DAY_DB ["day_meta"]
        dg["day_get()"] --> GC
        dgoc["day_get_or_create()"] --> GC
        dgw["day_get_week()"] --> GC
    end
```

---

## 8 — Dialog Dependencies (WorkApp → show_* → db_*)

```mermaid
flowchart LR
    WA["WorkApp actions"]

    WA -->|action_edit_entry| CE["show_content_edit()\ndialogs/content_edit.py"]
    WA -->|action_change_tag| TS["show_tag_select()\ndialogs/tag_select.py"]
    WA -->|action_delete_entry\naction_todo_delete| CF["show_confirm()\ndialogs/confirm.py"]
    WA -->|action_add_todo| NT["show_new_todo()\ndialogs/new_todo.py"]
    WA -->|action_todo_detail| TDL["show_todo_detail()\ndialogs/todo_detail.py"]
    WA -->|action_start_focus| SF["show_focus()\ndialogs/focus.py"]
    SF -->|on done| DB["show_debriefing()\ndialogs/debriefing.py"]
    WA -->|action_open_weekly| WK["show_weekly()\ndialogs/weekly.py"]

    CE -->|callback| lu["db.log_update()"]
    TS -->|callback| lu2["db.log_update()"]
    CF -->|callback| ld["db.log_delete() /\ntodo_set_status()"]
    NT -->|callback| ta["db.todo_add()"]
    TDL -->|callback| tu["db.todo_update()"]
    DB -->|callback| se["db.session_end()\ndb.log_add()\ndb.note_add()"]
    WK -->|reads| ws["db.week_summary()\ndb.day_get_week()"]
```
