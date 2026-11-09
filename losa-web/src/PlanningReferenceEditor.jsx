import {useEffect,useState} from "react";
import {api} from "./api";

const labels={flights:"Новый рейс",pilots:"Новый пилот",auditors:"Новый аудитор"};
const initial={flights:{number:"",departure:"",arrival:"",time:"",aircraft:""},pilots:{pilot_id:"",company:"",location:"",position:"",experience:"",type_experience:"",fmc_experience:""},auditors:{auditor_code:"",name:"",username:"",password:""}};
export default function PlanningReferenceEditor({onCreated,onBusy}){
 const [airportTarget,setAirportTarget]=useState(""),[airport,setAirport]=useState({airport_code:"",airport_name:""}),[airportError,setAirportError]=useState("");
 const [kind,setKind]=useState(""),[data,setData]=useState({}),[options,setOptions]=useState(null),[busy,setBusy]=useState(false),[error,setError]=useState(""),[message,setMessage]=useState("");
 useEffect(()=>{onBusy(Boolean(kind)||busy);},[kind,busy,onBusy]);
 useEffect(()=>()=>onBusy(false),[onBusy]);
 async function open(value){setAirportTarget("");setAirportError("");setKind(value);setData({...initial[value]});setError("");setMessage("");setOptions(null);setBusy(true);try{setOptions(await api.planningReference("options"));}catch(e){setError(e.message);}finally{setBusy(false);}}
 function field(key,label,items,type="text"){
  return <label className="field" key={key}><span>{label}</span>{items?<select disabled={busy} value={data[key]} onChange={e=>setData(v=>({...v,[key]:e.target.value}))}><option value="">Выберите</option>{items.map(x=><option key={x.id} value={x.id}>{x.label}</option>)}</select>:<input disabled={busy} type={type} min={type==="number"?0:undefined} autoComplete={key==="password"?"new-password":key==="username"?"off":undefined} value={data[key]} onChange={e=>setData(v=>({...v,[key]:e.target.value}))}/>}</label>;
 }
 async function saveAirport(){setBusy(true);setAirportError("");try{
  const saved=await api.planningReference("airports","POST",airport);
  setOptions(v=>({...v,airports:[...v.airports,{id:saved.id,label:saved.label}].sort((a,b)=>a.label.localeCompare(b.label))}));
  setData(v=>({...v,[airportTarget]:String(saved.id)}));setAirportTarget("");setAirport({airport_code:"",airport_name:""});
 }catch(e){setAirportError(e.message);}finally{setBusy(false);}}
 async function save(){setBusy(true);setError("");setMessage("");try{
  const payload={...data};
  const numeric=kind==="flights"?["departure","arrival","aircraft"]:kind==="pilots"?["pilot_id","company","location","experience","type_experience","fmc_experience"]:["auditor_code"];
  for(const key of numeric)payload[key]=payload[key]===""?null:Number(payload[key]);
  const result=await api.planningReference(kind,"POST",payload);
  setData({...initial[kind]});setKind("");
  try{await onCreated(kind,result.id);setMessage("Запись добавлена. Списки обновлены.");}catch{setMessage("Запись сохранена, но списки обновить не удалось. Закройте форму и обновите страницу; не создавайте запись повторно.");}
 }catch(e){setError(e.message);}finally{setBusy(false);}}
 return <section className="rt-card" onKeyDown={e=>{if(e.key==="Enter"&&e.target.tagName!=="BUTTON")e.preventDefault();}}><h3>Добавить в справочник</h3><div className="form-actions">{Object.entries(labels).map(([key,label])=><button type="button" className="outline" key={key} disabled={busy} onClick={()=>open(key)}>{label}</button>)}</div>
 {error&&<p className="notice error" role="alert">{error}</p>}{message&&<p className="notice" role="status">{message}</p>}
 {kind&&<div><h3>{labels[kind]}</h3>{!options&&!busy&&<button type="button" className="outline" onClick={()=>{setKind("");setError("");}}>Закрыть</button>}{!options&&busy&&<p>Загрузка справочников…</p>}{options&&<><div className="planner-grid">
 {kind==="flights"&&<>{field("number","Номер рейса")}{field("departure","Аэропорт вылета",options.airports)}{field("arrival","Аэропорт прилета",options.airports)}<div className="form-actions"><button type="button" className="outline" disabled={busy} onClick={()=>{setAirportTarget("departure");setAirport({airport_code:"",airport_name:""});setAirportError("");}}>Добавить аэропорт вылета</button><button type="button" className="outline" disabled={busy} onClick={()=>{setAirportTarget("arrival");setAirport({airport_code:"",airport_name:""});setAirportError("");}}>Добавить аэропорт прилета</button></div>{field("time","Время вылета (UTC)",null,"time")}{field("aircraft","Тип ВС",options.aircraft)}</>}
 {kind==="pilots"&&<>{field("pilot_id","Номер сотрудника",null,"number")}{field("company","Компания",options.companies)}{field("location","Местоположение",options.locations)}{field("position","Должность",options.positions)}{field("experience","Общий стаж, полных лет (необязательно)",null,"number")}{field("type_experience","Стаж на типе (необязательно)",null,"number")}{field("fmc_experience","Стаж на ВС с автоматическими системами (необязательно)",null,"number")}</>}
 {kind==="auditors"&&<>{field("auditor_code","Код аудитора",null,"number")}{field("name","ФИО аудитора")}{field("username","Логин для сайта и iPad")}{field("password","Пароль",null,"password")}</>}
 </div>{kind==="flights"&&airportTarget&&<section className="rt-card"><h4>{airportTarget==="departure"?"Новый аэропорт вылета":"Новый аэропорт прилета"}</h4><div className="planner-grid"><label className="field"><span>Код аэропорта</span><input maxLength={100} value={airport.airport_code} disabled={busy} onChange={e=>setAirport(v=>({...v,airport_code:e.target.value.toUpperCase()}))}/></label><label className="field"><span>Название аэропорта</span><input maxLength={100} value={airport.airport_name} disabled={busy} onChange={e=>setAirport(v=>({...v,airport_name:e.target.value}))}/></label></div>{airportError&&<p className="notice error" role="alert">{airportError}</p>}<div className="form-actions"><button type="button" className="outline" disabled={busy} onClick={()=>setAirportTarget("")}>Отмена добавления аэропорта</button><button type="button" className="primary" disabled={busy||!airport.airport_code.trim()||!airport.airport_name.trim()} onClick={saveAirport}>Сохранить аэропорт</button></div><p className="muted">Аэропорт сохраняется в общем справочнике и останется в нем, даже если отменить создание рейса.</p></section>}{kind==="auditors"&&<p className="muted">Будет создана учетная запись с ролью аудитора. Передайте логин и пароль аудитору.</p>}<div className="form-actions"><button type="button" className="outline" disabled={busy} onClick={()=>{setData({});setKind("");setError("");}}>Отмена</button><button type="button" className="primary" disabled={busy||Boolean(airportTarget)} onClick={save}>{busy?"Сохраняем…":"Добавить"}</button></div></> }</div>}
 </section>;
}
