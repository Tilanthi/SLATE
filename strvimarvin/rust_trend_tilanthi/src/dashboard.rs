use crate::wfo;
use anyhow::{Context, Result};
use serde::Serialize;
use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream};

pub fn serve(port: u16) -> Result<()> {
    let listener = TcpListener::bind(("127.0.0.1", port))
        .with_context(|| format!("bind dashboard server on 127.0.0.1:{port}"))?;
    println!("dashboard listening at http://127.0.0.1:{port}/dashboard");
    for stream in listener.incoming() {
        match stream {
            Ok(stream) => {
                if let Err(err) = handle(stream) {
                    eprintln!("dashboard request error: {err:#}");
                }
            }
            Err(err) => eprintln!("dashboard accept error: {err}"),
        }
    }
    Ok(())
}

fn handle(mut stream: TcpStream) -> Result<()> {
    let mut buffer = [0; 4096];
    let read = stream.read(&mut buffer)?;
    let request = String::from_utf8_lossy(&buffer[..read]);
    let path = request
        .lines()
        .next()
        .and_then(|line| line.split_whitespace().nth(1))
        .unwrap_or("/");

    match path {
        "/" | "/dashboard" => respond_html(&mut stream, dashboard_html()),
        "/api/status" => respond_json(&mut stream, &status_payload()?),
        "/api/runs" => respond_json(&mut stream, &wfo::list_runs()?),
        "/api/run-history" => respond_json(&mut stream, &wfo::run_history()?),
        "/api/checks" => respond_json(&mut stream, &wfo::read_checks()?),
        "/api/plan" => respond_json(&mut stream, &wfo::default_plan()),
        "/api/strategies" => respond_json(&mut stream, &wfo::strategy_rows(None)?),
        "/api/strategy-oos" => respond_json(&mut stream, &wfo::read_strategy_oos_results(None)?),
        path if path.starts_with("/api/runs/") && path.ends_with("/summary") => {
            let run_id = path
                .trim_start_matches("/api/runs/")
                .trim_end_matches("/summary")
                .trim_matches('/');
            match wfo::read_summary(run_id) {
                Ok(summary) => respond_json(&mut stream, &summary),
                Err(_) => respond_json(&mut stream, &serde_json::Value::Null),
            }
        }
        path if path.starts_with("/api/runs/") && path.ends_with("/strategy-oos") => {
            let run_id = path
                .trim_start_matches("/api/runs/")
                .trim_end_matches("/strategy-oos")
                .trim_matches('/');
            respond_json(&mut stream, &wfo::read_strategy_oos_results(Some(run_id))?)
        }
        path if path.starts_with("/api/runs/") && path.ends_with("/artifacts") => {
            let run_id = path
                .trim_start_matches("/api/runs/")
                .trim_end_matches("/artifacts")
                .trim_matches('/');
            respond_json(&mut stream, &wfo::read_artifacts(run_id)?)
        }
        path if path.starts_with("/api/runs/") && path.ends_with("/folds") => {
            let run_id = path
                .trim_start_matches("/api/runs/")
                .trim_end_matches("/folds")
                .trim_matches('/');
            respond_json(&mut stream, &wfo::read_fold_results(run_id)?)
        }
        path if path.starts_with("/api/runs/") && path.ends_with("/trades") => {
            let run_id = path
                .trim_start_matches("/api/runs/")
                .trim_end_matches("/trades")
                .trim_matches('/');
            respond_json(&mut stream, &wfo::read_recent_trades(run_id, 200)?)
        }
        path if path.starts_with("/api/runs/") && path.ends_with("/equity") => {
            let run_id = path
                .trim_start_matches("/api/runs/")
                .trim_end_matches("/equity")
                .trim_matches('/');
            respond_json(&mut stream, &wfo::read_equity_tail(run_id, 300)?)
        }
        path if path.starts_with("/api/runs/") && path.ends_with("/events") => {
            let run_id = path
                .trim_start_matches("/api/runs/")
                .trim_end_matches("/events")
                .trim_matches('/');
            respond_json(&mut stream, &wfo::read_events(run_id, 200)?)
        }
        _ => respond_not_found(&mut stream),
    }
}

#[derive(Debug, Serialize)]
struct StatusPayload {
    current: Option<wfo::RunStatus>,
    latest_test_state: String,
}

fn status_payload() -> Result<StatusPayload> {
    Ok(StatusPayload {
        current: wfo::current_status()?,
        latest_test_state: "not_run".to_string(),
    })
}

fn respond_json<T: Serialize>(stream: &mut TcpStream, value: &T) -> Result<()> {
    let body = serde_json::to_string_pretty(value)?;
    respond(
        stream,
        "200 OK",
        "application/json; charset=utf-8",
        body.as_bytes(),
    )
}

fn respond_html(stream: &mut TcpStream, body: &'static str) -> Result<()> {
    respond(
        stream,
        "200 OK",
        "text/html; charset=utf-8",
        body.as_bytes(),
    )
}

fn respond_not_found(stream: &mut TcpStream) -> Result<()> {
    respond(
        stream,
        "404 Not Found",
        "application/json; charset=utf-8",
        br#"{"error":"not_found"}"#,
    )
}

fn respond(stream: &mut TcpStream, status: &str, content_type: &str, body: &[u8]) -> Result<()> {
    write!(
        stream,
        "HTTP/1.1 {status}\r\nContent-Type: {content_type}\r\nContent-Length: {}\r\nCache-Control: no-store\r\nConnection: close\r\n\r\n",
        body.len()
    )?;
    stream.write_all(body)?;
    stream.flush()?;
    Ok(())
}

fn dashboard_html() -> &'static str {
    r#"<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Rust Trend WFO</title>
  <style>
    :root{color-scheme:dark;--bg:#0d1113;--panel:#141a1d;--panel2:#182023;--line:#2d383e;--text:#eef4f6;--muted:#9fadb4;--green:#55c985;--yellow:#dfb85f;--blue:#6db7e8;--red:#e27070;--gray:#8b969c}
    *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:12px/1.35 system-ui,-apple-system,Segoe UI,sans-serif}
    header{position:sticky;top:0;z-index:5;background:#101619;border-bottom:1px solid var(--line);padding:10px 14px;box-shadow:0 2px 14px rgba(0,0,0,.25)}
    .top{display:grid;grid-template-columns:minmax(180px,1fr) auto;gap:14px;align-items:center}.brand{display:flex;align-items:baseline;gap:10px;min-width:0}
    h1{font-size:15px;margin:0;font-weight:760}.run{color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    .clock{border:1px solid #27543f;background:#12271f;color:#dff7e9;border-radius:999px;padding:3px 8px;font-weight:720;white-space:nowrap}
    .status-line{display:grid;grid-template-columns:110px 1fr auto;gap:10px;align-items:center;margin-top:8px}.phase{font-weight:780}.active{color:#dce6ea;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.eta{color:var(--muted);white-space:nowrap}
    .bar{height:6px;background:#263239;border-radius:999px;overflow:hidden}.fill{height:100%;background:var(--green);width:0%}
    main{padding:12px 14px 20px;display:grid;gap:10px;max-width:1380px;margin:0 auto}.summary{display:grid;grid-template-columns:repeat(6,minmax(110px,1fr));gap:8px}
    .tile,.block{border:1px solid var(--line);background:var(--panel);border-radius:7px}.tile{padding:8px 10px}.label{color:var(--muted);font-size:10px;font-weight:760;text-transform:uppercase}.value{font-size:15px;font-weight:780;margin-top:3px;font-variant-numeric:tabular-nums}
    .block{overflow:hidden}.block-head{display:grid;grid-template-columns:minmax(220px,1fr) 90px 160px 90px;gap:10px;align-items:center;padding:9px 10px;border-bottom:1px solid var(--line);background:linear-gradient(90deg,#151c20,#12181b)}
    h2{font-size:13px;margin:0;font-weight:780}.meta{color:var(--muted);font-size:11px;margin-top:2px}.pill{display:inline-flex;justify-content:center;border-radius:999px;padding:3px 7px;border:1px solid var(--line);font-weight:760;text-transform:capitalize}
    .pill.queued{color:#e9d9ac;background:#2c291d;border-color:#5f5230}.pill.in-progress{color:#d9efff;background:#172635;border-color:#38617d}.pill.current{color:#e8fff2;background:#123223;border-color:#2d734b}.pill.complete{color:#e8fff2;background:#173126;border-color:#346b50}.pill.stopped{color:#ffdede;background:#321b1b;border-color:#774141}
    .progress-text{text-align:right;color:var(--muted);font-variant-numeric:tabular-nums}.portfolio{display:grid;grid-template-columns:minmax(520px,1fr) 280px;gap:12px;padding:9px 10px;border-bottom:1px solid var(--line);background:#111719}
    .metrics{display:grid;grid-template-columns:repeat(7,minmax(70px,1fr));gap:8px}.metric .label{font-size:9px}.metric .value{font-size:14px}.metric .value.gate-value{font-size:11px;line-height:1.2;white-space:normal}.pos{color:var(--green)}.neg{color:var(--red)}
    .chart{height:54px;border:1px solid #233038;background:#0c1113;border-radius:5px;overflow:hidden}.chart svg{display:block;width:100%;height:100%}.chart .line{fill:none;stroke-width:2}.chart .axis{stroke:#26333a;stroke-width:1}
    .warning{display:none;border:1px solid #7b5a25;background:#2b2112;color:#ffe3a6;border-radius:7px;padding:9px 10px;font-weight:760}
    .warning.show{display:block}
    table{width:100%;border-collapse:collapse;table-layout:fixed}th,td{padding:6px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:middle}th{color:var(--muted);font-size:10px;text-transform:uppercase;background:#151d21}td{font-variant-numeric:tabular-nums}
    th:nth-child(1),td:nth-child(1){width:92px}th:nth-child(2),td:nth-child(2),th:nth-child(3),td:nth-child(3),th:nth-child(4),td:nth-child(4),th:nth-child(5),td:nth-child(5),th:nth-child(6),td:nth-child(6){width:94px}th:nth-child(7),td:nth-child(7){width:260px}
    .empty{padding:12px 10px;color:var(--muted)}@media(max-width:920px){.summary{grid-template-columns:repeat(2,1fr)}.block-head{grid-template-columns:1fr;gap:6px}.status-line{grid-template-columns:1fr}.portfolio{grid-template-columns:1fr}.metrics{grid-template-columns:repeat(2,1fr)}table{min-width:820px}.table-wrap{overflow:auto}.top{grid-template-columns:1fr}}
  </style>
</head>
<body>
  <header>
    <div class="top"><div class="brand"><h1>Rust Trend WFO</h1><span class="run" id="runId">-</span></div><div class="clock" id="clock">-</div></div>
    <div class="status-line"><div class="phase" id="phase">-</div><div class="bar"><div class="fill" id="runFill"></div></div><div class="eta" id="eta">-</div></div>
    <div class="status-line"><div class="label">Current</div><div class="active" id="activeWork">-</div><div class="eta" id="runPct">0%</div></div>
  </header>
  <main>
    <div class="warning" id="modeWarning">Research-only optimizer mode: results are not clean point-in-time OOS validation.</div>
    <div class="summary">
      <div class="tile"><div class="label">Mode</div><div class="value" id="mode">-</div></div>
      <div class="tile"><div class="label">Offset</div><div class="value" id="offset">-</div></div>
      <div class="tile"><div class="label">Fold</div><div class="value" id="fold">-</div></div>
      <div class="tile"><div class="label">Complete</div><div class="value" id="complete">-</div></div>
      <div class="tile"><div class="label">In Progress</div><div class="value" id="inProgress">-</div></div>
      <div class="tile"><div class="label">Queued</div><div class="value" id="queued">-</div></div>
    </div>
    <div id="strategyList"></div>
  </main>
  <script>
    const $=id=>document.getElementById(id);
    async function json(path){const r=await fetch(path);if(!r.ok)throw new Error(path);return await r.json()}
    function esc(v){return String(v??'-').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
    function n(v,d=2){const x=Number(v);return Number.isFinite(x)?x.toFixed(d):'-'}
    function pct(v){const x=Number(v);return Number.isFinite(x)?x.toFixed(2)+'%':'-'}
    function int(v){const x=Number(v);return Number.isFinite(x)?x.toLocaleString():'-'}
    function cls(v){const x=Number(v);return x>0?'pos':x<0?'neg':''}
    function mmss(seconds){const s=Number(seconds);if(!Number.isFinite(s))return '-';const m=Math.floor(s/60),r=Math.floor(s%60);return `${m}m ${r}s`}
    function visualState(block,current){if(current?.phase==='Failed')return 'stopped';if(current?.active_indicator===block.indicator&&current?.active_timeframe===block.timeframe)return 'current';if(block.status==='complete')return 'complete';if(Number(block.progress_pct)>0)return 'in-progress';return 'queued'}
    function metric(label,value,className=''){return `<div class="metric"><div class="label">${esc(label)}</div><div class="value ${className}">${esc(value)}</div></div>`}
    function spark(points,tone='symbol',netReturn=0){
      if(!points||points.length<2)return '<div class="chart"></div>';
      const profitable=Number(netReturn)>0;
      const palette=tone==='portfolio'
        ? (profitable?['#6db7e8','rgba(109,183,232,.20)']:['#e27070','rgba(226,112,112,.18)'])
        : (profitable?['#55c985','rgba(85,201,133,.18)']:['#8b969c','rgba(139,150,156,.14)']);
      const w=260,h=54,p=4,xs=points.map((_,i)=>i),ys=points.map(p=>Number(p.equity)||0),min=Math.min(...ys),max=Math.max(...ys),span=Math.max(1e-9,max-min);
      const xy=(y,i)=>`${p+(i/(points.length-1))*(w-p*2)},${h-p-((y-min)/span)*(h-p*2)}`;
      const line=ys.map((y,i)=>(i?'L':'M')+xy(y,i)).join(' ');
      const area=`M${p},${h-p} `+ys.map((y,i)=>'L'+xy(y,i)).join(' ')+` L${w-p},${h-p} Z`;
      return `<div class="chart"><svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none"><line class="axis" x1="0" y1="${h-p}" x2="${w}" y2="${h-p}"/><path d="${area}" fill="${palette[1]}"/><path class="line" d="${line}" stroke="${palette[0]}"/></svg></div>`
    }
    function gateText(block){
      const g=block.candidate_gate||{};
      if(!block.portfolio)return 'pending';
      if(g.pass_candidate)return 'candidate';
      return `rejected: ${g.reason||'failed gate'}`;
    }
    function gateClass(block){
      const g=block.candidate_gate||{};
      if(g.pass_candidate)return 'gate-value pos';
      if(g.status==='pending'||!block.portfolio)return 'gate-value';
      return 'gate-value neg';
    }
    function metricsHtml(block){
      const m=block.portfolio, gate=metric('Candidate',gateText(block),gateClass(block));
      if(!m)return `<div class="metrics">${metric('Net','-')}${metric('Sharpe','-')}${metric('Max DD','-')}${metric('Trades','-')}${metric('Win Rate','-')}${metric('Profit Factor','-')}${gate}</div>`;
      return `<div class="metrics">${metric('Net',pct(m.net_return_pct),cls(m.net_return_pct))}${metric('Sharpe',n(m.sharpe,2))}${metric('Max DD',pct(m.max_drawdown_pct),'neg')}${metric('Trades',int(m.trades))}${metric('Win Rate',pct(m.win_rate))}${metric('Profit Factor',n(m.profit_factor,2))}${gate}</div>`;
    }
    function rowHtml(row){
      const m=row.metrics;
      return `<tr><td>${esc(row.symbol)}</td><td class="${cls(m.net_return_pct)}">${pct(m.net_return_pct)}</td><td>${n(m.sharpe,2)}</td><td>${pct(m.max_drawdown_pct)}</td><td>${int(m.trades)}</td><td>${pct(m.win_rate)}</td><td>${spark(m.equity_curve,'symbol',m.net_return_pct)}</td></tr>`;
    }
    function blockHtml(block,current){
      const state=visualState(block,current),p=Math.max(0,Math.min(100,Number(block.progress_pct)||0)),m=block.portfolio;
      const rows=(block.symbols||[]).map(rowHtml).join('');
      return `<article class="block">
        <div class="block-head">
          <div><h2>${esc(block.indicator)} · ${esc(block.timeframe)}</h2><div class="meta">${int(block.parameter_candidates)} candidates · ${esc(block.progress_label||'')}</div></div>
          <span class="pill ${state}">${state.replace('-',' ')}</span>
          <div class="bar"><div class="fill" style="width:${p}%"></div></div>
          <div class="progress-text">${p.toFixed(0)}%</div>
        </div>
        <div class="portfolio"><div>${metricsHtml(block)}</div>${spark(m?.equity_curve,'portfolio',m?.net_return_pct)}</div>
        <div class="table-wrap">${rows?`<table><tr><th>Symbol</th><th>Net Return</th><th>Sharpe</th><th>Max DD</th><th>Trades</th><th>Win Rate</th><th>Equity Curve</th></tr>${rows}</table>`:'<div class="empty">OOS result pending</div>'}</div>
      </article>`;
    }
    async function refresh(){
      const [status,history]=await Promise.all([json('/api/status'),json('/api/run-history')]);
      const current=status.current,runId=current?.run_id||history?.[0]?.run_id;
      const hist=(history||[]).find(r=>r.run_id===runId)||{};
      const mode=current?.optimizer_mode||hist.optimizer_mode||'-';
      $('clock').textContent=new Date().toLocaleTimeString();
      $('runId').textContent=runId||'-';
      $('phase').textContent=current?.phase||'-';
      const rp=Math.max(0,Math.min(100,Number(current?.progress_pct)||0));$('runFill').style.width=rp+'%';$('runPct').textContent=rp.toFixed(1)+'%';
      $('eta').textContent=current?.eta_seconds!=null?'ETA '+mmss(current.eta_seconds):'-';
      $('activeWork').textContent=current?.active_indicator?`${current.active_symbol||'-'} · ${current.active_indicator} · ${current.active_timeframe||'-'}`:(current?.message||'-');
      $('mode').textContent=mode==='point_in_time_fold_local'?'point-in-time':(mode==='retrospective_global_research_only'?'research-only':mode);
      $('offset').textContent=current?.active_offset_days!=null?String(current.active_offset_days):'-';
      $('fold').textContent=current?.active_fold_index!=null?`${Number(current.active_fold_index)+1}/${current.active_fold_count||'-'}`:'-';
      $('modeWarning').className='warning '+(mode==='retrospective_global_research_only'?'show':'');
      const blocks=runId?await json(`/api/runs/${runId}/strategy-oos`):await json('/api/strategy-oos');
      const complete=blocks.filter(b=>b.status==='complete').length,inProg=blocks.filter(b=>b.status!=='complete'&&Number(b.progress_pct)>0).length,queued=blocks.length-complete-inProg;
      $('complete').textContent=int(complete);$('inProgress').textContent=int(inProg);$('queued').textContent=int(queued);
      const best=blocks.filter(b=>b.candidate_gate?.pass_candidate).map(b=>b.portfolio?.net_return_pct).filter(v=>Number.isFinite(Number(v))).map(Number).sort((a,b)=>b-a)[0];
      $('strategyList').innerHTML=blocks.map(b=>blockHtml(b,current)).join('');
    }
    refresh().catch(console.error);setInterval(()=>refresh().catch(console.error),1500);
  </script>
</body>
</html>"#
}

#[allow(dead_code)]
fn dashboard_html_legacy() -> &'static str {
    r#"<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Rust Trend WFO</title>
  <style>
    :root {
      color-scheme: dark;
      --bg:#0f1214;
      --surface:#151a1d;
      --panel:#1d2428;
      --panel2:#222a2f;
      --line:#344047;
      --text:#f3f6f7;
      --muted:#b4c0c6;
      --soft:#d4dbdf;
      --accent:#56c596;
      --accent2:#89d7b4;
      --warn:#e0b761;
      --bad:#e36b6b;
    }
    * { box-sizing: border-box; }
    body { margin:0; font:12px/1.35 system-ui,-apple-system,Segoe UI,sans-serif; background:var(--bg); color:var(--text); }
    header {
      display:flex;
      align-items:center;
      justify-content:space-between;
      gap:14px;
      padding:9px 14px;
      border-bottom:1px solid var(--line);
      background:#101517;
      position:sticky;
      top:0;
      z-index:2;
    }
    h1 { margin:0; font-size:15px; font-weight:750; letter-spacing:0; }
    h2 { margin:0 0 8px; font-size:14px; font-weight:720; letter-spacing:0; }
    main { min-height:calc(100vh - 39px); }
    nav {
      display:flex;
      gap:6px;
      border-bottom:1px solid var(--line);
      padding:7px 14px;
      background:#121719;
      position:sticky;
      top:39px;
      z-index:1;
    }
    button {
      border:1px solid var(--line);
      background:var(--surface);
      color:var(--soft);
      padding:5px 9px;
      border-radius:6px;
      text-align:center;
      cursor:pointer;
      font-size:12px;
      font-weight:650;
      min-width:74px;
    }
    button.active { border-color:var(--accent); background:#1d2b27; color:#effff7; }
    section { display:none; padding:12px 14px; max-width:1760px; }
    section.active { display:block; }
    .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(145px,1fr)); gap:8px; margin-bottom:10px; }
    .card {
      border:1px solid var(--line);
      border-radius:6px;
      background:var(--panel);
      padding:8px 10px;
      min-height:60px;
      box-shadow:0 1px 0 rgba(255,255,255,.03) inset;
    }
    .label { color:var(--muted); font-size:10px; font-weight:700; text-transform:uppercase; }
    .value {
      font-size:16px;
      line-height:1.2;
      font-weight:760;
      margin-top:5px;
      overflow-wrap:anywhere;
      color:var(--text);
    }
    .small-value { font-size:11px; line-height:1.3; font-weight:650; color:var(--soft); }
    .bar { height:6px; background:#2c373d; border-radius:999px; overflow:hidden; margin-top:6px; }
    .bar.compact { height:5px; margin-top:4px; min-width:72px; }
    .fill { height:100%; background:var(--accent); width:0%; }
    .table-wrap {
      border:1px solid var(--line);
      border-radius:6px;
      overflow:auto;
      background:var(--surface);
      max-height:calc(100vh - 190px);
    }
    .table-wrap.short { max-height:260px; margin-bottom:10px; }
    table { width:100%; border-collapse:collapse; min-width:860px; font-size:12px; }
    th,td { border-bottom:1px solid var(--line); padding:5px 7px; text-align:left; vertical-align:middle; }
    th { color:var(--soft); font-weight:750; background:#182024; position:sticky; top:0; z-index:1; }
    td { color:#e4eaed; }
    pre {
      white-space:pre-wrap;
      overflow:auto;
      max-height:calc(100vh - 190px);
      border:1px solid var(--line);
      border-radius:6px;
      padding:10px;
      background:#0b0f10;
      color:#dfe7ea;
      font-size:11px;
      line-height:1.45;
    }
    .muted { color:var(--muted); }
    .status {
      display:inline-block;
      min-width:68px;
      border-radius:999px;
      padding:3px 7px;
      text-align:center;
      font-size:11px;
      font-weight:750;
      background:#2a3237;
      color:#dce5e8;
    }
    .status.complete { background:#173329; color:#dff7eb; border:1px solid #326a52; }
    .status.implemented { background:#173329; color:#dff7eb; border:1px solid #326a52; }
    .status.running { background:#1b2f3d; color:#dff2ff; border:1px solid #3f6f8f; }
    .status.pending { background:#302d22; color:#f0dfb2; border:1px solid #635633; }
    .status.not_in_grid { background:#272d31; color:#c9d3d8; border:1px solid #4a565d; }
    .status.regime_gate { background:#263244; color:#dbe8ff; border:1px solid #536b91; }
    .status.not_applicable_v1 { background:#34282b; color:#ffdfe6; border:1px solid #72515b; }
    .status.ok { background:#173329; color:#dff7eb; border:1px solid #326a52; }
    .status.too_sparse, .status.too_active, .status.low_profit_factor, .status.low_average_trade_edge, .status.nonpositive_net { background:#3a1d1d; color:#ffdede; border:1px solid #844343; }
    .status.pass { background:#173329; color:#dff7eb; border:1px solid #326a52; }
    .status.fail { background:#3a1d1d; color:#ffdede; border:1px solid #844343; }
    .status.not_recorded { background:#302d22; color:#f0dfb2; border:1px solid #635633; }
    .num { font-variant-numeric:tabular-nums; white-space:nowrap; }
    .section-title { display:flex; align-items:center; justify-content:space-between; gap:10px; margin:0 0 8px; }
    .section-title h2 { margin:0; }
    .stack { display:grid; gap:10px; }
    .subhead { margin:2px 0 6px; color:var(--soft); font-size:11px; font-weight:750; text-transform:uppercase; }
    .note { color:var(--muted); max-width:420px; overflow-wrap:anywhere; }
    .status-pill {
      display:inline-flex;
      align-items:center;
      gap:8px;
      color:#e9fff4;
      border:1px solid #326a52;
      background:#173329;
      border-radius:999px;
      padding:4px 8px;
      font-weight:700;
      font-size:11px;
    }
    .dot { width:7px; height:7px; border-radius:50%; background:var(--accent); }
    @media (max-width: 860px) {
      body { font-size:12px; }
      header { padding:10px 12px; align-items:flex-start; flex-direction:column; }
      nav { top:65px; overflow:auto; padding:7px 10px; }
      button { padding:6px 9px; font-size:12px; min-width:72px; }
      section { padding:10px; }
      .value { font-size:15px; }
      .grid { grid-template-columns:repeat(auto-fit,minmax(130px,1fr)); }
    }
  </style>
</head>
<body>
  <header><h1>Rust Trend WFO</h1><div class="status-pill"><span class="dot"></span><span id="updated">waiting</span></div></header>
  <main>
    <nav>
      <button class="active" data-view="overview">Overview</button>
      <button data-view="strategies">Strategies</button>
      <button data-view="folds">Folds</button>
      <button data-view="runs">Runs</button>
      <button data-view="artifacts">Artifacts</button>
      <button data-view="checks">Checks</button>
      <button data-view="logs">Logs</button>
    </nav>
    <section id="overview" class="active">
      <div class="section-title"><h2>Overview</h2><span class="muted" id="activeRunLabel">-</span></div>
      <div class="grid">
        <div class="card"><div class="label">Phase</div><div class="value" id="phase">-</div><div class="bar"><div class="fill" id="progress"></div></div></div>
        <div class="card"><div class="label">Net Return</div><div class="value" id="netReturn">-</div></div>
        <div class="card"><div class="label">Drawdown</div><div class="value" id="drawdown">-</div></div>
        <div class="card"><div class="label">Trades</div><div class="value" id="trades">-</div></div>
        <div class="card"><div class="label">Sharpe</div><div class="value" id="sharpe">-</div></div>
        <div class="card"><div class="label">Exposure</div><div class="value" id="exposure">-</div></div>
        <div class="card"><div class="label">Long Exposure</div><div class="value" id="longExposure">-</div></div>
        <div class="card"><div class="label">Short Exposure</div><div class="value" id="shortExposure">-</div></div>
        <div class="card"><div class="label">Avg Net Exposure</div><div class="value" id="netExposure">-</div></div>
        <div class="card"><div class="label">Longest Stagnation</div><div class="value" id="stagnation">-</div></div>
        <div class="card"><div class="label">Max Exposure</div><div class="value" id="maxExposure">-</div></div>
        <div class="card"><div class="label">Schedule</div><div class="value small-value" id="schedule">-</div></div>
        <div class="card"><div class="label">Min Profit Factor</div><div class="value" id="minProfitFactor">-</div></div>
        <div class="card"><div class="label">Wide Candidates</div><div class="value" id="candidateCount">-</div></div>
        <div class="card"><div class="label">Deferred</div><div class="value small-value" id="deferred">-</div></div>
      </div>
      <div class="stack">
        <div>
          <div class="subhead">Recent Runs</div>
          <div class="table-wrap"><table id="overviewRuns"></table></div>
        </div>
      </div>
    </section>
    <section id="strategies">
      <div class="section-title"><h2>Strategies</h2><span class="muted">indicator x timeframe families</span></div>
      <div class="grid">
        <div class="card"><div class="label">Catalog Strategies</div><div class="value" id="strategyFamilies">-</div></div>
        <div class="card"><div class="label">Runnable</div><div class="value" id="strategyRunnable">-</div></div>
        <div class="card"><div class="label">Parameter Candidates</div><div class="value" id="strategyCandidates">-</div></div>
        <div class="card"><div class="label">Completed Families</div><div class="value" id="strategyComplete">-</div></div>
        <div class="card"><div class="label">Best Score</div><div class="value" id="strategyBest">-</div></div>
      </div>
      <div class="subhead">Implementation Catalog</div>
      <div class="table-wrap short"><table id="implementationTable"></table></div>
      <div class="subhead">Runnable Progress</div>
      <div class="table-wrap"><table id="strategiesTable"></table></div>
    </section>
    <section id="folds">
      <div class="section-title"><h2>Folds</h2><span class="muted">best scored candidate by fold</span></div>
      <div class="grid">
        <div class="card"><div class="label">Folds</div><div class="value" id="foldCount">-</div></div>
        <div class="card"><div class="label">Best Fold Score</div><div class="value" id="bestFoldScore">-</div></div>
        <div class="card"><div class="label">Recent Trades</div><div class="value" id="recentTradeCount">-</div></div>
        <div class="card"><div class="label">Equity Samples</div><div class="value" id="equitySamples">-</div></div>
      </div>
      <div class="stack">
        <div>
          <div class="subhead">Fold Results</div>
          <div class="table-wrap"><table id="foldResults"></table></div>
        </div>
        <div>
          <div class="subhead">Recent Trades</div>
          <div class="table-wrap"><table id="recentTrades"></table></div>
        </div>
      </div>
    </section>
    <section id="runs">
      <div class="section-title"><h2>Runs</h2><span class="muted">history with result metrics</span></div>
      <div class="table-wrap"><table id="runsTable"></table></div>
    </section>
    <section id="artifacts">
      <div class="section-title"><h2>Artifacts</h2><span class="muted" id="artifactRunLabel">-</span></div>
      <div class="table-wrap"><table id="artifactsTable"></table></div>
    </section>
    <section id="checks">
      <div class="section-title"><h2>Checks</h2><span class="muted">persisted verification status</span></div>
      <div class="table-wrap"><table id="checksTable"></table></div>
    </section>
    <section id="logs">
      <div class="section-title"><h2>Logs</h2><span class="muted" id="logRunLabel">-</span></div>
      <div class="table-wrap"><table id="eventsTable"></table></div>
    </section>
  </main>
  <script>
    const $ = id => document.getElementById(id);
    document.querySelectorAll('button[data-view]').forEach(btn => btn.onclick = () => {
      document.querySelectorAll('button,section').forEach(el => el.classList.remove('active'));
      btn.classList.add('active'); $(btn.dataset.view).classList.add('active');
    });
    async function json(path){ const r = await fetch(path); if(!r.ok) throw new Error(path); return await r.json(); }
    function esc(v){ return String(v ?? '-').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
    function pct(n){ return Number.isFinite(n) ? n.toFixed(2) + '%' : '-'; }
    function num(n, d=2){ return Number.isFinite(Number(n)) ? Number(n).toFixed(d) : '-'; }
    function int(n){ return Number.isFinite(Number(n)) ? Number(n).toLocaleString() : '-'; }
    function day(ms){ return Number.isFinite(Number(ms)) ? new Date(Number(ms)).toISOString().slice(0,10) : '-'; }
    function stamp(v){ return v ? String(v).replace('T',' ').replace('Z',' UTC').slice(0,23) : '-'; }
    function statusBadge(v){ const s = String(v ?? 'unknown'); return `<span class="status ${esc(s)}">${esc(s)}</span>`; }
    function progressCell(v, label=''){
      const p = Math.max(0, Math.min(100, Number(v) || 0));
      const text = label ? `${esc(label)} · ${p.toFixed(0)}%` : `${p.toFixed(0)}%`;
      return `<div class="num">${text}</div><div class="bar compact"><div class="fill" style="width:${p}%"></div></div>`;
    }
    async function refresh(){
      const [plan,status,history,strategies,checks] = await Promise.all([
        json('/api/plan'), json('/api/status'), json('/api/run-history'), json('/api/strategies'), json('/api/checks')
      ]);
      $('updated').textContent = new Date().toLocaleTimeString();
      const cur = status.current;
      const runId = cur?.run_id || history[0]?.run_id;
      $('activeRunLabel').textContent = runId || '-';
      $('artifactRunLabel').textContent = runId || '-';
      $('logRunLabel').textContent = runId || '-';
      $('schedule').textContent = `${plan.config.is_weeks}w IS / ${plan.config.oos_weeks}w OOS / ${plan.config.step_weeks}w step`;
      $('minProfitFactor').textContent = num(plan.config.min_profit_factor, 2);
      $('candidateCount').textContent = plan.candidate_count;
      $('deferred').textContent = plan.not_applicable_v1.join(', ');
      const implementation = plan.implementation_status || [];
      const runnableCatalog = implementation.filter(s => s.runnable);
      const runnableProgress = strategies.filter(s => s.runnable);
      const completed = runnableProgress.filter(s => s.status === 'complete');
      const totalCandidates = runnableProgress.reduce((sum, s) => sum + s.parameter_candidates, 0);
      const bestScore = strategies.reduce((best, s) => Math.max(best, Number(s.best_score) || 0), 0);
      $('strategyFamilies').textContent = implementation.length || strategies.length;
      $('strategyRunnable').textContent = runnableCatalog.length || runnableProgress.length;
      $('strategyCandidates').textContent = totalCandidates.toLocaleString();
      $('strategyComplete').textContent = `${completed.length} / ${runnableProgress.length || strategies.length}`;
      $('strategyBest').textContent = bestScore.toFixed(3);
      $('implementationTable').innerHTML = '<tr><th>Strategy</th><th>Family</th><th>Impl</th><th>Runnable</th><th>Grid Candidates</th><th>Note</th></tr>' + implementation.map(s => {
        return `<tr><td>${esc(s.indicator)}</td><td>${esc(s.family)}</td><td>${statusBadge(s.implementation_status)}</td><td>${s.runnable ? 'yes' : 'no'}</td><td class="num">${int(s.grid_candidates)}</td><td class="note">${esc(s.note)}</td></tr>`;
      }).join('');
      $('strategiesTable').innerHTML = '<tr><th>Indicator</th><th>TF</th><th>Impl</th><th>Candidates</th><th>Run Status</th><th>Symbol Coverage</th><th>Best</th><th>IS Net</th><th>IS DD</th><th>Best Yr Trades</th></tr>' + strategies.map(s => {
        return `<tr><td>${esc(s.indicator)}</td><td class="num">${esc(s.timeframe)}</td><td>${statusBadge(s.implementation_status)}</td><td class="num">${int(s.parameter_candidates)}</td><td>${statusBadge(s.status)}</td><td>${progressCell(s.progress_pct, s.progress_label)}</td><td class="num">${num(s.best_score,3)}</td><td class="num">${pct(Number(s.net_return_pct))}</td><td class="num">${pct(Number(s.max_drawdown_pct))}</td><td class="num">${int(s.trades)}</td></tr>`;
      }).join('');
      if(cur){
        $('phase').textContent = cur.phase;
        $('progress').style.width = Math.max(0, Math.min(100, cur.progress_pct)) + '%';
      }
      $('overviewRuns').innerHTML = renderRuns(history.slice(0,6));
      $('runsTable').innerHTML = renderRuns(history);
      $('checksTable').innerHTML = '<tr><th>Check</th><th>Status</th><th>Command</th><th>Details</th><th>Finished</th></tr>' + checks.map(c => `<tr><td>${esc(c.name)}</td><td>${statusBadge(c.status)}</td><td>${esc(c.command)}</td><td>${esc(c.details)}</td><td class="num">${stamp(c.finished_at)}</td></tr>`).join('');
      if(runId){
        const [summary,events,folds,artifacts,trades,equity] = await Promise.all([
          json(`/api/runs/${runId}/summary`).catch(() => null),
          json(`/api/runs/${runId}/events`).catch(() => []),
          json(`/api/runs/${runId}/folds`).catch(() => []),
          json(`/api/runs/${runId}/artifacts`).catch(() => []),
          json(`/api/runs/${runId}/trades`).catch(() => []),
          json(`/api/runs/${runId}/equity`).catch(() => [])
        ]);
        if(summary){
          $('netReturn').textContent = pct(summary.net_return_pct);
          $('drawdown').textContent = pct(summary.max_drawdown_pct);
          $('trades').textContent = int(summary.trades);
          $('sharpe').textContent = num(summary.sharpe,2);
          $('exposure').textContent = pct(Number(summary.exposure_pct));
          $('longExposure').textContent = pct(Number(summary.long_exposure_pct));
          $('shortExposure').textContent = pct(Number(summary.short_exposure_pct));
          $('netExposure').textContent = '$' + int(summary.average_net_exposure_notional);
          $('stagnation').textContent = int(summary.longest_stagnation_minutes) + 'm';
          $('maxExposure').textContent = '$' + int(summary.max_exposure_notional);
        }
        $('foldCount').textContent = folds.length;
        $('bestFoldScore').textContent = num(folds.reduce((best, f) => Math.max(best, Number(f.score) || 0), 0),3);
        $('recentTradeCount').textContent = int(trades.length);
        $('equitySamples').textContent = int(equity.length);
        $('foldResults').innerHTML = '<tr><th>Fold</th><th>Symbol</th><th>Candidate</th><th>Score</th><th>IS Net</th><th>IS DD</th><th>IS PF</th><th>Min PF</th><th>Avg Trade</th><th>Min Avg</th><th>IS Trades</th><th>Trade Band</th><th>Trade Fit</th><th>Quality Fit</th></tr>' + folds.map(f => `<tr><td class="num">${f.fold_index}</td><td>${esc(f.symbol)}</td><td class="num">${f.candidate_id}</td><td class="num">${num(f.score,3)}</td><td class="num">${pct(Number(f.net_return_pct))}</td><td class="num">${pct(Number(f.max_drawdown_pct))}</td><td class="num">${num(f.profit_factor,2)}</td><td class="num">${num(f.min_profit_factor,2)}</td><td class="num">${pct(Number(f.average_trade_return_pct))}</td><td class="num">${pct(Number(f.min_average_trade_return_pct))}</td><td class="num">${int(f.trades)}</td><td class="num">${int(f.min_trades)}-${int(f.max_trades)}</td><td>${statusBadge(f.trade_fit)}</td><td>${statusBadge(f.quality_fit)}</td></tr>`).join('');
        $('recentTrades').innerHTML = '<tr><th>Exit Date</th><th>Symbol</th><th>Side</th><th>Entry</th><th>Exit</th><th>PnL</th><th>Return</th><th>Reason</th></tr>' + trades.slice().reverse().map(t => `<tr><td class="num">${day(t.exit_time_ms)}</td><td>${esc(t.symbol)}</td><td>${esc(t.side)}</td><td class="num">${num(t.entry_price,4)}</td><td class="num">${num(t.exit_price,4)}</td><td class="num">${num(t.pnl,2)}</td><td class="num">${pct(Number(t.return_pct))}</td><td>${esc(t.exit_reason)}</td></tr>`).join('');
        $('artifactsTable').innerHTML = '<tr><th>Artifact</th><th>Rows</th><th>Size</th><th>Modified</th><th>Path</th></tr>' + artifacts.map(a => `<tr><td>${esc(a.name)}</td><td class="num">${a.rows == null ? '-' : int(a.rows)}</td><td class="num">${int(a.bytes)}</td><td class="num">${stamp(a.modified_at)}</td><td>${esc(a.path)}</td></tr>`).join('');
        $('eventsTable').innerHTML = '<tr><th>Time</th><th>Kind</th><th>Message</th></tr>' + events.slice().reverse().map(e => `<tr><td class="num">${stamp(e.ts)}</td><td>${esc(e.kind)}</td><td>${esc(e.message)}</td></tr>`).join('');
      }
    }
    function renderRuns(rows){
      return '<tr><th>Run</th><th>Phase</th><th>Progress</th><th>Grid</th><th>Folds</th><th>Candidates</th><th>Trades</th><th>Net</th><th>DD</th><th>Sharpe</th><th>Updated</th></tr>' +
        rows.map(r => `<tr><td>${esc(r.run_id)}</td><td>${statusBadge(r.phase)}</td><td>${progressCell(r.progress_pct)}</td><td>${esc(r.grid)}</td><td class="num">${int(r.folds)}</td><td class="num">${int(r.candidates)}</td><td class="num">${int(r.trades)}</td><td class="num">${pct(Number(r.net_return_pct))}</td><td class="num">${pct(Number(r.max_drawdown_pct))}</td><td class="num">${num(r.sharpe,2)}</td><td class="num">${stamp(r.updated_at)}</td></tr>`).join('');
    }
    refresh().catch(err => console.error(err));
    setInterval(() => refresh().catch(err => console.error(err)), 1500);
  </script>
</body>
</html>"#
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn status_payload_serializes() {
        let payload = StatusPayload {
            current: None,
            latest_test_state: "not_run".to_string(),
        };

        let json = serde_json::to_string(&payload).unwrap();

        assert!(json.contains("latest_test_state"));
    }
}
