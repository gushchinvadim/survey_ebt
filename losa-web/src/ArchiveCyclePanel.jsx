import {useEffect,useState} from "react";
import {api} from "./api";

export default function ArchiveCyclePanel({cycleId,refreshSignal=0,disabled=false,onArchived}) {
 const [data,setData]=useState(null),[error,setError]=useState(""),[busy,setBusy]=useState(false),[confirm,setConfirm]=useState(false),[message,setMessage]=useState("");
 async function load(){setConfirm(false);setError("");setBusy(true);try{setData(await api.roundTable(`${cycleId}/archive/`));}catch(e){setError(e.message);}finally{setBusy(false);}}
 useEffect(()=>{let active=true;setConfirm(false);setData(null);setError("");api.roundTable(`${cycleId}/archive/`).then(d=>{if(active)setData(d);}).catch(e=>{if(active)setError(e.message);});return()=>{active=false;};},[cycleId,refreshSignal]);
 async function archive(){if(!data?.ready||busy||disabled)return;setBusy(true);setError("");try{
  const result=await api.roundTable(`${cycleId}/archive/`,"POST",{revision:data.revision,report_id:data.report_id,digest:data.digest});
  setData(result);setConfirm(false);setMessage(`Проверки отправлены в архив: ${result.archived_count}. После обновления назначений они исчезнут из списка аудитора, в том числе на iPad.`);await onArchived?.();
 }catch(e){setError(e.message);setConfirm(false);}finally{setBusy(false);}}
 return <section className="rt-card"><h2>Архив проверок цикла</h2><p className="muted">После анализа и выпуска отчета координатор отправляет проверки в серверный архив. Листы, согласованные тексты и PDF остаются в базе. В назначениях аудиторов архивные проверки больше не показываются.</p>
 {error&&<div className="notice error" role="alert">{error}</div>}{message&&<div className="notice" role="status">{message}</div>}
 {!data&&!error&&<p role="status">Проверяем возможность архивирования…</p>}
 {data&&<>{data.already_archived?<p className="notice">Все проверки цикла уже находятся в архиве. Отчеты доступны для скачивания.</p>:<>
 <p>Проверок: {data.assignments.length}. Уже в архиве: {data.archived_count}. {data.report_version?`Отчет: версия ${data.report_version}.`:"Отчет еще не выпущен."}</p>
 {!!data.reasons.length&&<ul>{data.reasons.map(reason=><li key={reason}>{reason}</li>)}</ul>}
 <details><summary>Проверки, которые будут скрыты из назначений</summary><ul>{data.assignments.filter(a=>!a.archived).map(a=><li key={a.id}>{a.number}</li>)}</ul></details>
 {!confirm?<button className="primary" type="button" disabled={!data.ready||busy||disabled} onClick={()=>setConfirm(true)}>Отправить проверки цикла в архив</button>:<div className="notice"><p>Подтвердите архивирование {data.assignments.filter(a=>!a.archived).length} проверок. Они перестанут отображаться у аудиторов. Данные и отчеты сохранятся на сервере.</p><button className="primary" type="button" disabled={busy||disabled} onClick={archive}>{busy?"Архивируем…":"Подтвердить архивирование"}</button> <button className="outline" type="button" disabled={busy} onClick={()=>setConfirm(false)}>Отмена</button></div>}
 </>}</>}
 <button className="outline" type="button" disabled={busy||disabled} onClick={load}>Обновить проверку условий</button>
 <p className="muted">Возврат из архива доступен координатору в админке назначенных проверок. Физическая очистка локальных копий на iPad выполняется отдельно.</p></section>;
}
