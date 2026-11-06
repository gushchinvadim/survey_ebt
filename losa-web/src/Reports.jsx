import {useEffect, useState} from "react";
import {api} from "./api";
import ReportPanel from "./ReportPanel";
import "./round-table.css";

export default function Reports({cycleId}) {
 const [data,setData]=useState(null),[error,setError]=useState(""),[dirty,setDirty]=useState(false);
 useEffect(()=>{let active=true;api.roundTable(cycleId?`${cycleId}/`:"").then(d=>{if(active)setData(d);}).catch(e=>{if(active)setError(e.message);});return()=>{active=false;};},[cycleId]);
 useEffect(()=>{const guard=e=>{if(dirty){e.preventDefault();e.returnValue="";}};window.addEventListener("beforeunload",guard);return()=>window.removeEventListener("beforeunload",guard);},[dirty]);
 function leave(e){if(dirty&&!window.confirm("В отчете есть несохраненные тексты. Перейти без сохранения?"))e.preventDefault();}
 return <section className="page workspace rt-page"><a className="back-link" href={cycleId?"#reports":"#coordinator"} onClick={leave}>← {cycleId?"Все отчеты":"Пространство координатора"}</a><p className="eyebrow">Координатор программы · Документы цикла</p><h1>{cycleId?data?.cycle.name||"Подготовка отчета":"Отчеты PDF"}</h1><p className="muted">Итоговый отчет с диаграммами и процентами и отдельный документ с решениями круглого стола.</p>
 {error&&<div className="notice error" role="alert">{error}</div>}{!data&&!error&&<p role="status">Загружаем циклы и документы…</p>}
 {data&&(cycleId?<>
 <div className="notice">{data.cycle.closed?"Обсуждение завершено. Можно сформировать новую версию документов.":"Цикл еще обсуждается. Выпуск PDF станет доступен после завершения круглого стола."} <a href={`#round-table/${cycleId}`} onClick={leave}>Открыть круглый стол →</a></div>
 <ReportPanel cycle={data.cycle} onDirty={setDirty} expanded/>
 </>:<section className="rt-card"><h2>Выберите цикл</h2><p className="muted">Завершенные циклы готовы к выпуску. Ранее выпущенные версии доступны в карточке цикла.</p>{data.cycles.map(c=><a className="rt-cycle-link" key={c.id} href={`#reports/${c.id}`}><strong>{c.name}</strong><span>{c.count} наблюдений · {c.closed?"Обсуждение завершено · Сформировать отчет":"Обсуждение в работе · Подготовить тексты"} →</span></a>)}{!data.cycles.length&&<p>Циклов пока нет. <a href="#round-table">Создать цикл круглого стола →</a></p>}</section>)}
 </section>;
}
