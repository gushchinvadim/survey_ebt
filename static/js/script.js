// логин

// document.addEventListener('DOMContentLoaded', function() {
//     const isLoggedIn = localStorage.getItem('isLoggedIn') === 'true';

//     if (isLoggedIn) {
//         document.querySelector('.guest-menu').style.display = 'none';
//         document.querySelector('.user-menu').style.display = 'block';

//         document.getElementById('logout-btn').addEventListener('click', function(e) {
//             e.preventDefault();
//             localStorage.removeItem('isLoggedIn');
//             window.location.href = 'login-form.html';
//         });
//     }
// });

// гамбургер
document.addEventListener('DOMContentLoaded', function () {
    const burger = document.querySelector('.burger-menu');
    const menu = document.querySelector('.header-menu');

    if (!burger || !menu) {
        console.error('Элементы бургера или меню не найдены!');
        return;
    }

    burger.addEventListener('click', function () {
        menu.classList.toggle('active');
        console.log('Класс active переключён'); // ← Проверка в консоли
    });
});

// автоподстройка высоты textarea = facts

function autoResizeTextarea(textarea) {
    textarea.addEventListener('input', function () {
        this.style.height = 'auto';
        this.style.height = Math.min(this.scrollHeight, 600) + 'px';
    });

    // Также вызовем один раз при загрузке — если внутри уже есть текст
    if (textarea.value) {
        textarea.dispatchEvent(new Event('input'));
    }
}

// Применяем ко всем textarea с классом .facts
document.querySelectorAll('.facts').forEach(autoResizeTextarea);


// массив данных ступеней

const STAGES = [

    {
        id: "crew_demografy",
        title: "Демогфия экипажа",
        stageNumber: 1,
        fields: [
             'departure', 'arrival', 'aircraft_type', 'pilot_flying',
            'flight_delay', 'base_ad_capt', 'base_ad_fo',
            'captain_total_experience', 'captain_type_experience', 'captain_fmc_experience',
            'copilot_total_experience', 'copilot_type_experience', 'copilot_fmc_experience',
            'work_together', 'flight_date',
        ]
    },
    {
        id: "preflight_taxing",
        title: "Предполетная подготовка. Выруливание на взлетную позицию",
        stageNumber: 2,
        fields: [
            "facts_for_preflight_taxing", "flight_plan_sop_brief", "flight_plan_discussion",
            "load_crew_members_brief", "control_unexpected_situations", "coontrol_flight_instruments",
            "load_crew_members", "attentiveness", "automatic_system_control", "critical_assessment_plans", "request_for_clarification",
            "conviction"
        ]
    },
    {
        id: "takeoff_climb",
        title: "Взлет. Набор высоты",
        stageNumber: 3,
        fields: [
            "facts_takeoff_climb", "coontrol_flight_instruments_to_climb", "load_crew_members_to",
            "attentiveness_to", "control_auto_system_to", "critical_assessment_plans_to", "request_for_clarification_to",
            "conviction_to",
        ]
    },
    {
        id: "cruise",
        title: "Крейсерский режим",
        stageNumber: 4,
        fields: [
            "facts_cruise",
        ]
    },
    {
        id: "descent",
        title: "Снижение. Заход на посадку. Посадка и руление",
        stageNumber: 5,
        fields: [
            "init_descent_brief", "start_of_descent_fms", "start_of_descent_trajectory",
            "approach_type", "type_of_control", "descent_trajectory", "flap_settings","weather_condition",
            "approach_speed_1500",  "rate_of_des_1500", "engine_control_1500", "landing_config_1500",
            "descent_on_given_trajectory_1500", "approach_speed_1000",  "rate_of_des_1000", "engine_control_1000", "landing_config_1000",
            "descent_on_given_trajectory_1000", "approach_speed_500",  "rate_of_des_500", "engine_control_500", "landing_config_500",
            "descent_on_given_trajectory_500", "landing_brief_facts", "top_of_descent_facts", "trans_level_facts", "10000_feet_proc_facts",
            "deceleration_facts", "faf_om_facts", "compliance_basic_criteria_facts", "flare_touchdown_facts", "taxing_parking_facts",
            "flight_plan_sop_brief_landing", "flight_plan_discussion_landing", "load_crew_members_brief_landing", "control_unexpected_situations_landing",
            "coontrol_flight_instruments_landing", "load_crew_members_landing", "attentiveness_landing", "managing_automatic_systems_landing",
            "critical_assessment_plans_landing", "request_for_clarification_landing", "conviction_landing",
        ]
    },
    {
        id: "total_mark",
        title: "Оценка полета в целом",
        stageNumber: 6,
        fields: [
            "total_mark_facts", "clear_communication_mark", "captain_as_leader_mark", "preflight_instructing_flight_attendants",
            "preflight_instructing_flight_attendants_mark", "capitain_contribution_effective_work", "copilot_contribution_effective_work",
            "overall_assessment_crew_performance",
        ]
    },
    {
        id: "mistake",
        title: "Контролирование ошибок",
        stageNumber: 7,
        fields: [
            "describe_mistake_",
            "mistake_code_",
            "fase_of_flight_",
            "mistake_type_",
            "mistake_code_and_describe_",
            "whu_made_mistake_",
            "who_noticed_mistake_",
            "crew_reaction_mistake_",
            "result_of_mistake_",
            "on_treatment_reason_",
            "sucсessful_action_",
            "status_change_code_safety_",
            "who_recognize_status_",
            "mistake_crew_reaction_",
            "status_changing_result_",

        ],
        isDynamic: true // флаг, чтобы saveStage понимал, что это динамический блок
    },
    {
        id: "threatment",
        title: "Контролирование факторов угрозы",
        stageNumber: 8,
        fields: [
            // Эти поля будут собираться динамически — по индексам
            "describe_threatment_",
            "threatment_code_",
            "fase_of_flight_",
            "threatment_control_",
            "threatment_crew_action_"
        ],
        isDynamic: true // флаг, чтобы saveStage понимал, что это динамический блок
    },
]

// валидация пустых полей

function validateStage(stageId, fieldNames = null) {
    const container = document.getElementById(stageId);
    if (!container) return { valid: true };

    const selectors = fieldNames
        ? fieldNames.map(name => `[name="${name}"], [id="${name}"]`).join(', ')
        : 'input:not([type="hidden"]), select, textarea';

    const fields = container.querySelectorAll(selectors);
    const errors = [];

    // Сначала снимаем все ошибки
    fields.forEach(field => {
        field.classList.remove('field-error');
    });

    fields.forEach(field => {
        const name = field.name || field.id;
        const label = container.querySelector(`label[for="${name}"]`)?.innerText || field.name || field.id;
        let value = field.value.trim ? field.value.trim() : field.value;

        if (field.hasAttribute('required')) {
            if ((field.tagName === 'SELECT' && value === '') ||
                (field.tagName === 'TEXTAREA' && value === '') ||
                (field.tagName === 'INPUT' && value === '')) {

                errors.push(`«${label}» — ${field.tagName === 'SELECT' ? 'выберите значение' : 'заполните поле'}`);
                field.classList.add('field-error');
            }
        }
    });

    return {
        valid: errors.length === 0,
        errors: errors
    };
}

// === Функция: Сохранить текущий этап в localStorage ===

function saveStage(stageNumber) {
    const stage = STAGES.find(s => s.stageNumber === stageNumber);
    if (!stage) {
        alert(`❌ Этап ${stageNumber} не найден в конфигурации.`);
        return;
    }

    // ✅ Валидация
    const validation = validateStage(stage.id, stage.fields);
    if (!validation.valid) {
        let message = `⚠️ Пожалуйста, заполните следующие поля:\n\n`;
        message += validation.errors.join('\n');
        alert(message);
        return;
    }

    // ✅ Сбор данных и сохранение
    const formData = collectFormDataForStage(stage.id, stage.fields);
    const key = `stage_${stageNumber}_${stage.id}`;

    localStorage.setItem(key, JSON.stringify(formData));
    console.log(`💾 Этап ${stageNumber} "${stage.title}" сохранён:`, formData);

    alert(`✅ Данные этапа ${stageNumber}: "${stage.title}" успешно сохранены!`);
}




function validateStage(stageId, fields) {
    const errors = [];

    // Особая логика для динамического этапа "threatment"
    if (stageId === "threatment") {
        const container = document.getElementById('threatment-container');
        const blocks = container.querySelectorAll('.stage');

        blocks.forEach((block, index) => {
            const idx = index + 1;

            const fieldMap = {
                [`describe_threatment_${idx}`]: "Описание угрозы",
                [`threatment_code_${idx}`]: "Код угрозы",
                [`fase_of_flight_${idx}`]: "Этап полёта",
                [`threatment_control_${idx}`]: "Эффективность контроля",
                [`threatment_crew_action_${idx}`]: "Действия экипажа"
            };

            for (let [fieldName, label] of Object.entries(fieldMap)) {
                const el = block.querySelector(`[name="${fieldName}"]`);
                if (el && el.hasAttribute('required') && !el.value.trim()) {
                    errors.push(`Блок #${idx}: "${label}" — обязательно для заполнения`);
                }
            }
        });

        return {
            valid: errors.length === 0,
            errors: errors
        };
    }

// Особая логика для динамического этапа "mistake"
    if (stageId === "mistake") {
        const container = document.getElementById('mistake-container');
        const blocks = container.querySelectorAll('.stage'); // предполагаем, что каждый блок имеет класс .stage

        blocks.forEach((block, index) => {
            const idx = index + 1;

            const fieldMap = {
                [`describe_mistake_${idx}`]: "Описание ошибки",
                [`mistake_code_${idx}`]: "Код ошибки",
                [`fase_of_flight_${idx}`]: "Этап полёта",
                [`mistake_type_${idx}`]: "Тип ошибки",
                [`mistake_code_and_describe_${idx}`]: "Код и описание ошибки",
                [`whu_made_mistake_${idx}`]: "Кто совершил ошибку",
                [`who_noticed_mistake_${idx}`]: "Кто заметил ошибку",
                [`crew_reaction_mistake_${idx}`]: "Реакция экипажа на ошибку",
                [`result_of_mistake_${idx}`]: "Результат ошибки",
                [`on_treatment_reason_${idx}`]: "По причине фактора угрозы",
                [`sucсessful_action_${idx}`]: "Успешные действия",
                [`status_change_code_safety_${idx}`]: "Изменение статуса безопасности",
                [`who_recognize_status_${idx}`]: "Кто распознал изменение статуса",
                [`mistake_crew_reaction_${idx}`]: "Реакция экипажа на изменение статуса",
                [`status_changing_result_${idx}`]: "Результат изменения статуса"
            };

            for (let [fieldName, label] of Object.entries(fieldMap)) {
                const el = block.querySelector(`[name="${fieldName}"]`);
                if (el && el.hasAttribute('required') && !el.value.trim()) {
                    errors.push(`Блок #${idx}: "${label}" — обязательно для заполнения`);
                }
            }
        });

        return {
            valid: errors.length === 0,
            errors: errors
        };
    }

    // СТАРАЯ ЛОГИКА — для обычных этапов
    fields.forEach(field => {
        const el = document.querySelector(`[name="${field}"]`);
        if (el && el.hasAttribute('required') && !el.value.trim()) {
            errors.push(`"${el.closest('.form-row')?.querySelector('label')?.innerText || field}" — обязательно для заполнения`);
        }
    });

    return {
        valid: errors.length === 0,
        errors: errors
    };
}



function collectFormDataForStage(stageId, fields) {
    // Особая логика для динамического этапа "threatment"
    if (stageId === "threatment") {
        const container = document.getElementById('threatment-container');
        const blocks = container.querySelectorAll('.stage');
        const threats = [];

        blocks.forEach((block, index) => {
            const idx = index + 1;

            const threat = {
                // id: idx,
                describe_threatment: block.querySelector(`[name="describe_threatment_${idx}"]`)?.value || '',
                threatment_code: block.querySelector(`[name="threatment_code_${idx}"]`)?.value || '',
                fase_of_flight: block.querySelector(`[name="fase_of_flight_${idx}"]`)?.value || '',
                threatment_control: block.querySelector(`[name="threatment_control_${idx}"]`)?.value || '',
                threatment_crew_action: block.querySelector(`[name="threatment_crew_action_${idx}"]`)?.value || ''
            };

            threats.push(threat);
        });

        return threats; // возвращаем массив объектов
    }
// Особая логика для динамического этапа "mistake"
    if (stageId === "mistake") {
        const container = document.getElementById('mistake-container');
        const blocks = container.querySelectorAll('.stage');

         const formData = {};

        blocks.forEach((block, index) => {
            const idx = index + 1;
            const blockData = {};

            const fieldNames = [
                `describe_mistake_${idx}`,
                `mistake_code_${idx}`,
                `fase_of_flight_${idx}`,
                `mistake_type_${idx}`,
                `mistake_code_and_describe_${idx}`,
                `whu_made_mistake_${idx}`,
                `who_noticed_mistake_${idx}`,
                `crew_reaction_mistake_${idx}`,
                `result_of_mistake_${idx}`,
                `on_treatment_reason_${idx}`,
                `sucсessful_action_${idx}`,
                `status_change_code_safety_${idx}`,
                `who_recognize_status_${idx}`,
                `mistake_crew_reaction_${idx}`,
                `status_changing_result_${idx}`
            ];
                        fieldNames.forEach(fieldName => {
                const el = block.querySelector(`[name="${fieldName}"]`);
                if (el) {
                    blockData[fieldName] = el.type === 'checkbox' || el.type === 'radio'
                        ? el.checked
                        : el.value;
                }
            });

            formData[`block_${idx}`] = blockData;
        });

        return formData;
    }
    // СТАРАЯ ЛОГИКА — для обычных этапов
    const formData = {};
    fields.forEach(field => {
        const el = document.querySelector(`[name="${field}"]`);
        if (el) {
            formData[field] = el.value;
        }
    });
    return formData;
}


// Функция — собрать все сохранённые этапы
function collectAllSavedStages() {
    const allData = {};
    const missing = [];

    STAGES.forEach(stage => {
        const key = `stage_${stage.stageNumber}_${stage.id}`;
        const saved = localStorage.getItem(key);

        if (saved) {
            allData[stage.id] = JSON.parse(saved);
        } else {
            missing.push(stage.title);
        }
    });

    return {
        data: allData,
        missing: missing,
        isComplete: missing.length === 0
    };
}

// Функция — отправить всё вместе на сервер
async function submitAllStages() {
    const result = collectAllSavedStages();

    if (!result.isComplete) {
        alert(`❌ Не все этапы сохранены:\n- ${result.missing.join('\n- ')}`);
        return;
    }

    const payload = {
        report_type: 'losa_current_flight_data', // 👈 Укажите тип отчёта
        submitted_at: new Date().toISOString(),
        stages: result.data
    };

    // const apiUrl = 'https://your-api-domain.com/api/flight-report'; // 👈 ЗАМЕНИТЕ НА СВОЙ URL!
    const apiUrl = 'https://httpbin.org/post';

    try {
        const response = await fetch(apiUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                // 🔐 Если нужна авторизация:
                // 'Authorization': 'Bearer YOUR_TOKEN'
            },
            body: JSON.stringify(payload)
        });

        if (response.ok) {
            const result = await response.json();
            alert('✅ Весь отчёт успешно отправлен на сервер!');
            console.log('Ответ сервера:', result);

            // 🗑️ Опционально: очистить localStorage после успешной отправки
            STAGES.forEach(stage => {
                localStorage.removeItem(`stage_${stage.stageNumber}_${stage.id}`);
            });
            alert('💾 Данные удалены из локального хранилища.');

        } else {
            const errorText = await response.text();
            throw new Error(`Ошибка сервера (${response.status}): ${errorText}`);
        }
    } catch (error) {
        console.error('❌ Ошибка отправки:', error);
        alert(`❌ Не удалось отправить отчёт:\n${error.message}`);
    }
}

// // индикатор прогресса

 function getCompletedStages() {
     return Object.keys(localStorage).filter(key => key.startsWith('stage_'));
 }



// Кнопка ссылка "в начало страницы"

document.addEventListener('DOMContentLoaded', function () {
    const backToTopButton = document.getElementById('backToTop');

    if (!backToTopButton) {
        console.error('Кнопка #backToTop не найдена!');
        return;
    }

    function toggleBackToTopButton() {
        if (window.pageYOffset > 100) {
            backToTopButton.classList.add('show');
        } else {
            backToTopButton.classList.remove('show');
        }
    }

    backToTopButton.addEventListener('click', function () {
        window.scrollTo({
            top: 0,
            behavior: 'smooth'
        });
    });

    window.addEventListener('scroll', toggleBackToTopButton);
    toggleBackToTopButton(); // ← ЭТО СПАСЁТ КНОПКУ!
});

// динамический контент контролирование факторов угроз
document.addEventListener('DOMContentLoaded', function () {
    // Счётчик начинается с 0 — будет увеличиваться при создании блока
    let threatmentCounter = 0;

    // === ФУНКЦИЯ: добавить блок угрозы с опциональными данными ===
    function addThreatmentBlock(data = null) {
        threatmentCounter++;

        const container = document.getElementById('threatment-container');
        if (!container) {
            console.error('Контейнер #threatment-container не найден!');
            return;
        }

        const idx = threatmentCounter; // используем текущий индекс

        const block = document.createElement('div');
        block.className = 'stage';
        block.dataset.stage = 'threatment';
        block.innerHTML = `
            <div class="pilot-group">
                <h4>КОНТРОЛИРОВАНИЕ ФАКТОРОВ УГРОЗЫ (${idx})</h4>

                <label for="describe_threatment_${idx}">ОПИШИТЕ УГРОЗУ<br></label>
                <textarea id="describe_threatment_${idx}" class="facts" name="describe_threatment_${idx}" required placeholder="Записать все что Вы считаете нужным">${data?.describe_threatment || ''}</textarea>

                <div class="form-row">
                    <label for="threatment_code_${idx}" class="form-label">Код угрозы</label>
                    <div class="form-controls">
                        <select id="threatment_code_${idx}" name="threatment_code_${idx}" required>
                            <option value="">Выбрать из списка</option>
                            <option value="1">1. Неблагоприятные погодные условия</option>
                            <option value="2">2. Сложный рельеф местности</option>
                            <option value="3">3. Интенсивное движение (на земле или в воздухе), TCAS</option>
                            <option value="4">4. Аэропорт: недостатки в конструкции, разметка, состояние ВПП</option>
                            <option value="5">5. TCAS RA/TA</option>
                            <option value="20">20. Неполадки в работе систем ВС</option>
                            <option value="21">21. Отказ или отклонения в работе автоматической системы управления</option>
                            <option value="22">22. Нарушение связи: бортовые радиосредства, ATIS, ACARS</option>
                            <option value="30">30. Дефицит времени: отсрочки, ОТР, опоздание пилота или задержка ВС</option>
                            <option value="31">31. Неудачный заход на посадку</option>
                            <option value="32">32. Направление на запасной аэродром</option>
                            <option value="33">33. Незнакомый для экипажа аэропорт</option>
                            <option value="34">34. Прочие трудности: максимальный взлетный вес, прерванный взлет</option>
                            <option value="40">40. В кабине экипажа/рассредоточенность/ помехи в работе</option>
                            <option value="41">41. Ошибка бортпроводника</option>
                            <option value="50">50. Команды диспетчера: отмены разрешений, поздние команды об изменении</option>
                            <option value="51">51. Ошибка диспетчера</option>
                            <option value="52">52. Языковые проблемы</option>
                            <option value="53">53. Использование нестандартной фразеологии</option>
                            <option value="54">54. Перегруженность эфира</option>
                            <option value="55">55. Схожесть позывных сигналов</option>
                            <option value="80">80. Ситуация, связанная с ТОиР</option>
                            <option value="81">81. Ошибка при ТОиР</option>
                            <option value="82">82. Недоразумение при наземном обслуживании</option>
                            <option value="83">83. Ошибка команды наземного обслуживания</option>
                            <option value="84">84. Недоразумение, связанное с отправлением груза и почты</option>
                            <option value="85">85. Ошибка службы отправления груза и почты</option>
                            <option value="86">86. Недоразумение, связанное с расписанием работы экипажей</option>
                            <option value="87">87. Документация: неполный комплект карт, неправильные инструкции</option>
                            <option value="99">99. Прочие ФУ</option>
                        </select>
                    </div>
                </div>

                <div class="form-row">
                    <label for="fase_of_flight_${idx}" class="form-label">Этап полета</label>
                    <div class="form-controls">
                        <select id="fase_of_flight_${idx}" name="fase_of_flight_${idx}" required>
                            <option value="">Выбрать из списка</option>
                            <option value="preflight-taxing">1. Предполетная подготовка. Выруливание на взлет</option>
                            <option value="takeoff_climb">2. Взлет. Набор высоты</option>
                            <option value="cruise">3. Крейсерский режим</option>
                            <option value="descent_landing">4. Снижение. Заход на посадку. Посадка</option>
                            <option value="taxi_to_park">5. Руление к месту остановки</option>
                        </select>
                    </div>
                </div>

                <div class="form-row">
                    <label for="threatment_control_${idx}" class="form-label">Был ли контроль за ФУ эффективным</label>
                    <div class="form-controls">
                        <select id="threatment_control_${idx}" name="threatment_control_${idx}" required>
                            <option value="">Выбрать из списка</option>
                            <option value="normal">Да</option>
                            <option value="abnormal">Нет</option>
                        </select>
                    </div>
                </div>

                <div class="form-row">
                    <label for="threatment_crew_action_${idx}" class="form-label">Правильные или неправильные действия экипажа по контролю за ФУ</label>
                    <div class="form-controls">
                        <select id="threatment_crew_action_${idx}" name="threatment_crew_action_${idx}" required>
                            <option value="">Выбрать из списка</option>
                            <option value="normal">Правильные</option>
                            <option value="abnormal">Не правильные</option>
                        </select>
                    </div>
                </div>

                <button type="button" class="form-submit remove-btn" onclick="this.closest('.stage').remove()">Удалить угрозу</button>
            </div>
        `;

        container.appendChild(block);

        // Устанавливаем значения из данных (если переданы)
        if (data) {
            const setIfExists = (selector, value) => {
                const el = block.querySelector(selector);
                if (el) el.value = value;
            };

            setIfExists(`[name="describe_threatment_${idx}"]`, data.describe_threatment || '');
            setIfExists(`[name="threatment_code_${idx}"]`, data.threatment_code || '');
            setIfExists(`[name="fase_of_flight_${idx}"]`, data.fase_of_flight || '');
            setIfExists(`[name="threatment_control_${idx}"]`, data.threatment_control || '');
            setIfExists(`[name="threatment_crew_action_${idx}"]`, data.threatment_crew_action || '');
        }
    }

    // === ПРИВЯЗКА КНОПКИ "ДОБАВИТЬ" ===
    const addButton = document.getElementById('add-threatment');
    if (addButton) {
        addButton.addEventListener('click', () => addThreatmentBlock());
    } else {
        console.error('Кнопка #add-threatment не найдена в DOM!');
    }

    // === ВОССТАНОВЛЕНИЕ ИЗ localStorage ===
    const saved = localStorage.getItem('stage_8_threatment');
    const container = document.getElementById('threatment-container');

    if (saved && container) {
        try {
            const threats = JSON.parse(saved);
            if (Array.isArray(threats) && threats.length > 0) {
                // Очищаем контейнер (на случай повторной инициализации)
                container.innerHTML = '';
                threatmentCounter = 0; // сбрасываем счётчик

                threats.forEach(threatData => {
                    addThreatmentBlock(threatData);
                });
            } else {
                // Если данных нет — создаём первый блок
                addThreatmentBlock();
            }
        } catch (e) {
            console.error('Ошибка при восстановлении данных этапа 8:', e);
            // На всякий случай создаём блок
            addThreatmentBlock();
        }
    } else if (container) {
        // Нет сохранённых данных — создаём первый блок
        addThreatmentBlock();
    }
});



// БЛОК ОШИБОК
 let mistakeCounter = 0;

 document.addEventListener('DOMContentLoaded', async function () {


//     === ФУНКЦИЯ ДОБАВЛЕНИЯ БЛОКА ОШИБОК ===
     function addMistakeBlock() {
         mistakeCounter++;

         const container = document.getElementById('mistake-container');
         if (!container) {
             console.error('Контейнер #mistake-container не найден!');
             return;
         }

         const block = document.createElement('div');
         block.className = 'stage';
         block.dataset.stage = 'mistake';
         block.innerHTML = `
             <div class="pilot-group">
                 <h4>ОПИСАНИЕ ОШИБКИ (${mistakeCounter})</h4>

                 <label for="describe_mistake_${mistakeCounter}">Опишите ошибку в действиях экипажа и связанное с этим изменение состояния безопасности воздушного судна</label>
                 <textarea id="describe_mistake_${mistakeCounter}" class="facts" name="describe_mistake_${mistakeCounter}" required placeholder="Записать все что Вы считаете нужным"></textarea>

                 <!-- Фаза полета -->
                 <div class="form-row">
                     <label for="fase_of_flight_${mistakeCounter}" class="form-label">Фаза полета</label>
                     <div class="form-controls">
                         <select id="fase_of_flight_${mistakeCounter}" name="fase_of_flight_${mistakeCounter}" required>
                             <option value="">Выбрать из списка</option>
                             <option value="preflight-taxing">1. Предполетная подготовка. Выруливание на взлет</option>
                             <option value="takeoff_climb">2. Взлет. Набор высоты</option>
                             <option value="cruise">3. Крейсерский режим</option>
                             <option value="descent_landing">4. Снижение. Заход на посадку. Посадка</option>
                             <option value="taxi_to_park">5. Руление к месту остановки</option>
                         </select>
                     </div>
                 </div>

                <div class="form-row">
                    <label for="mistake_type_${mistakeCounter}" class="form-label">Тип ошибки</label>
                    <div class="form-controls">
                        <select id="mistake_type_${mistakeCounter}" name="mistake_type_${mistakeCounter}" required>
                            <option value="0">Выбрать из списка</option>
                             <option value="1">Нет</option>
// Опции будут добавлены JS
                        </select>
                    </div>
                </div>
//Код ошибки и описание будут добавлены JS
                <div class="form-row">
                    <label for="mistake_code_and_describe_${mistakeCounter}" class="form-label">Код ошибки</label>
                    <div class="form-controls">
                        <select id="mistake_code_and_describe_${mistakeCounter}" name="mistake_code_and_describe_${mistakeCounter}" required>
                            <option value="0">Выбрать из списка</option>
                            <option value="1">Нет</option>
// Опции будут добавлены после выбора типа JS
                        </select>
                    </div>
                </div>

                 <!-- Кто допустил -->
                 <div class="form-row">
                     <label for="whu_made_mistake_${mistakeCounter}" class="form-label">Кто допустил ошибку</label>
                     <div class="form-controls">
                         <select id="whu_made_mistake_${mistakeCounter}" name="whu_made_mistake_${mistakeCounter}" required>
                             <option value="">Выбрать из списка</option>
                             <option value="capitain">КВС</option>
                             <option value="copilot">Второй пилот</option>
                         </select>
                     </div>
                 </div>

                 <!-- Кто заметил -->
                 <div class="form-row">
                     <label for="who_noticed_mistake_${mistakeCounter}" class="form-label">Кто заметил ошибку</label>
                     <div class="form-controls">
                         <select id="who_noticed_mistake_${mistakeCounter}" name="who_noticed_mistake_${mistakeCounter}" required>
                             <option value="">Выбрать из списка</option>
                             <option value="1">КВС</option>
                             <option value="2">Второй пилот</option>
                             <option value="4">Сменный пилот</option>
                             <option value="5">Наблюдатель</option>
                             <option value="6">Весь экипаж</option>
                             <option value="7">Никто</option>
                             <option value="8">Служба ОрВД</option>
                             <option value="9">Бортпроводник</option>
                             <option value="10">Служба отправления груза и почты</option>
                             <option value="11">Команда наземного обслуживания</option>
                             <option value="12">ТоиР ВС</option>
                             <option value="20">Системы ВС</option>
                             <option value="99">Прочие</option>
                         </select>
                     </div>
                 </div>

                 <!-- Реакция экипажа на ошибку -->
                 <div class="form-row">
                     <label for="crew_reaction_mistake_${mistakeCounter}" class="form-label">Реакция экипажа на ошибку</label>
                     <div class="form-controls">
                         <select id="crew_reaction_mistake_${mistakeCounter}" name="crew_reaction_mistake_${mistakeCounter}" required>
                             <option value="">Выбрать из списка</option>
                             <option value="1">Захват</option>
                             <option value="2">Раздражение</option>
                             <option value="3">Невосприятие</option>
                         </select>
                     </div>
                 </div>

                 <!-- Результат ошибки -->
                 <div class="form-row">
                     <label for="result_of_mistake_${mistakeCounter}" class="form-label">Результат ошибки</label>
                     <div class="form-controls">
                         <select id="result_of_mistake_${mistakeCounter}" name="result_of_mistake_${mistakeCounter}" required>
                             <option value="">Выбрать из списка</option>
                             <option value="1">Отсутствие последствий</option>
                             <option value="2">Изменение состояния безопасности ВС</option>
                             <option value="3">Дополнительная ошибка</option>
                         </select>
                     </div>
                 </div>
             </div>

             <!-- КОНТРОЛИРОВАНИЕ ОШИБКИ -->
             <div class="pilot-group">
                 <h4>КОНТРОЛИРОВАНИЕ ОШИБКИ</h4>

                 <!-- По причине ФУ -->
                 <div class="form-row">
                     <label for="on_treatment_reason_${mistakeCounter}" class="form-label">По причине ФУ</label>
                     <div class="form-controls">
                         <select id="on_treatment_reason_${mistakeCounter}" name="on_treatment_reason_${mistakeCounter}" required>
                             <option value="">Выбрать из списка</option>
                             <option value="0">0. Угрозы не было</option>
                             <option value="1">1. Неблагоприятные погодные условия</option>
                             <option value="2">2. Сложный рельеф местности</option>
                             <option value="3">3. Интенсивное движение (на земле или в воздухе), TCAS</option>
                             <option value="4">4. Аэропорт: недостатки в конструкции, разметка, состояние ВПП</option>
                             <option value="5">5. TCAS RA/TA</option>
                             <option value="20">20. Неполадки в работе систем ВС</option>
                             <option value="21">21. Отказ или отклонения в работе автоматической системы управления</option>
                             <option value="22">22. Нарушение связи: бортовые радиосредства, ATIS, ACARS</option>
                             <option value="30">30. Дефицит времени: отсрочки, ОТР, опоздание пилота или задержка ВС</option>
                             <option value="31">31. Неудачный заход на посадку</option>
                             <option value="32">32. Направление на запасной аэродром</option>
                             <option value="33">33. Незнакомый для экипажа аэропорт</option>
                             <option value="34">34. Прочие трудности: максимальный взлетный вес, прерванный взлет</option>
                             <option value="40">40. В кабине экипажа/рассредоточенность/ помехи в работе</option>
                             <option value="41">41. Ошибка бортпроводника</option>
                             <option value="50">50. Команды диспетчера: отмены разрешений, поздние команды</option>
                             <option value="51">51. Ошибка диспетчера</option>
                             <option value="52">52. Языковые проблемы</option>
                             <option value="53">53. Использование нестандартной фразеологии</option>
                             <option value="54">54. Перегруженность эфира</option>
                             <option value="55">55. Схожесть позывных сигналов</option>
                             <option value="80">80. Ситуация, связанная с ТОиР</option>
                             <option value="81">81. Ошибка при ТОиР</option>
                             <option value="82">82. Недоразумение при наземном обслуживании</option>
                             <option value="83">83. Ошибка команды наземного обслуживания</option>
                             <option value="84">84. Недоразумение, связанное с отправлением груза и почты</option>
                             <option value="85">85. Ошибка службы отправления груза и почты</option>
                             <option value="86">86. Недоразумение, связанное с расписанием работы экипажей</option>
                             <option value="87">87. Документация: неполный комплект карт, неправильные инструкции</option>
                             <option value="99">99. Прочие ФУ</option>
                         </select>
                     </div>
                 </div>

                 <!-- Удачные (или неудачные) действия экипажа в связи с ошибкой -->
                 <div class="form-row">
                     <label for="sucсessful_action_${mistakeCounter}" class="form-label">Удачные действия экипажа в связи с ошибкой</label>
                     <div class="form-controls">
                         <select id="sucсessful_action_${mistakeCounter}" name="sucсessful_action_${mistakeCounter}" required>
                             <option value="">Выбрать из списка</option>
                             <option value="sucсessful">Удачные</option>
                             <option value="unsucсessful">Неудачные</option>
                         </select>
                     </div>
                 </div>

                 <!-- Код изменения состояния безопасности ВС -->
                 <div class="form-row">
                     <label for="status_change_code_safety_${mistakeCounter}" class="form-label">Код изменения состояния безопасности ВС</label>
                     <div class="form-controls">
                         <select id="status_change_code_safety_${mistakeCounter}" name="status_change_code_safety_${mistakeCounter}" required>
                             <option value="">Выбрать из списка</option>
                             <option value="0">Изменения не было</option>
                             <option value="1">Конфигурация ВС: органы управления</option>
                             <option value="2">Конфигурация ВС: системы (например; топливная, электро...)</option>
                             <option value="3">Конфигурация ВС: система автоматического управления</option>
                             <option value="4">Конфигурация ВС: двигатели</option>
                             <option value="20">ВС на земле: Следование к заданной ВПП</option>
                             <option value="21">ВС на земле: Вторжение на ВПП</option>
                             <option value="22">ВС на земле: Следование не к заданной РД или стоянке</option>
                             <option value="23">ВС на земле: Вторжение на РД или стоянку</option>
                             <option value="24">ВС на земле: Подруливание не к тому посадочному выходу</option>
                             <option value="40">Пилотирование: Отклонение в вертикальной плоскости</option>
                             <option value="41">Пилотирование: Боковое отклонение</option>
                             <option value="42">Пилотирование: Заход в зону погодных явлений без необходимости</option>
                             <option value="43">Пилотирование: Нарушение воздушного пространства</option>
                             <option value="44">Пилотирование: Слишком высокая скорость полета</option>
                             <option value="45">Пилотирование: Слишком низкая скорость полета</option>
                             <option value="46">Пилотирование: Временная потеря управления (положение ВС)</option>
                             <option value="47">Пилотирование: Чрезмерное кренение ВС</option>
                             <option value="48">Пилотирование: Превышение предельных параметров пилотирования ВС</option>
                             <option value="80">Заход: Отклонение вверх от глиссады или от посадочной траектории</option>
                             <option value="81">Заход: Отклонение вниз от глиссады или от посадочной траектории</option>
                             <option value="82">Заход: Нестабилизированный заход на посадку</option>
                             <option value="83">Посадка: Длительная посадка: нестабилизированный заход на посадку</option>
                             <option value="84">Посадка: Грубая посадка</option>
                             <option value="85">Посадка: Неустойчивая посадка</option>
                             <option value="86">Посадка: Приземление со смещением от оси ВПП</option>
                             <option value="87">Посадка: Посадка за пределами зоны</option>
                             <option value="99">Прочие изменения состояния безопасности полета</option>
                         </select>
                     </div>
                 </div>

                 <!-- Кто определил изменение состояния безопасности ВС -->
                 <div class="form-row">
                     <label for="who_recognize_status_${mistakeCounter}" class="form-label">Кто определил изменение состояния безопасности ВС</label>
                     <div class="form-controls">
                         <select id="who_recognize_status_${mistakeCounter}" name="who_recognize_status_${mistakeCounter}" required>
                             <option value="">Выбрать из списка</option>
                             <option value="0">Изменения не было</option>
                             <option value="1">КВС</option>
                             <option value="2">Второй пилот</option>
                             <option value="4">Сменный пилот</option>
                             <option value="5">Наблюдатель</option>
                             <option value="6">Весь экипаж</option>
                             <option value="7">Никто</option>
                             <option value="8">Служба ОрВД</option>
                             <option value="9">Бортпроводник</option>
                             <option value="10">Служба отправления груза и почты</option>
                             <option value="11">Команда наземного обслуживания</option>
                             <option value="12">ТоиР ВС</option>
                             <option value="20">Системы ВС</option>
                             <option value="99">Прочие</option>
                         </select>
                     </div>
                 </div>

                 <!-- Реакция экипажа на изменение состояния безопасности ВС -->
                 <div class="form-row">
                     <label for="mistake_crew_reaction_${mistakeCounter}" class="form-label">Реакция экипажа на изменение состояния безопасности ВС</label>
                     <div class="form-controls">
                         <select id="mistake_crew_reaction_${mistakeCounter}" name="mistake_crew_reaction_${mistakeCounter}" required>
                             <option value="">Выбрать из списка</option>
                             <option value="Изменения не было">Изменения не было</option>
                             <option value="Спокойная">Спокойная</option>
                             <option value="Раздраженная">Раздраженная</option>
                             <option value="Отсутствие реакции">Отсутствие реакции</option>
                         </select>
                     </div>
                 </div>

                 <!-- Результат изменения состояния безопасности ВС -->
                 <div class="form-row">
                     <label for="status_changing_result_${mistakeCounter}" class="form-label">Результат изменения состояния безопасности ВС</label>
                     <div class="form-controls">
                         <select id="status_changing_result_${mistakeCounter}" name="status_changing_result_${mistakeCounter}" required>
                             <option value="">Выбрать из списка</option>
                             <option value="1">Отсутствие последствий</option>
                             <option value="2">Изменение состояния безопасности ВС</option>
                             <option value="3">Дополнительная ошибка</option>
                         </select>
                     </div>
                 </div>

             </div>

         `;

         container.appendChild(block);
}

//     // === ИНИЦИАЛИЗИРУЕМ СЕЛЕКТЫ В ЭТОМ БЛОКЕ ===
//     if (errorDataGrouped) {
//         const typeSelect = block.querySelector(`#mistake_type_${mistakeCounter}`);
//         const codeSelect = block.querySelector(`#mistake_code_and_describe_${mistakeCounter}`);

         // Заполняем типы ошибок
//         typeSelect.innerHTML = '<option value="">Выбрать тип ошибки</option>';
//         Object.keys(errorDataGrouped).forEach(group => {
//             const opt = document.createElement('option');
//             opt.value = group;
//             opt.textContent = group;
//             typeSelect.appendChild(opt);
//         });
//
//         // Обработчик выбора типа
//         typeSelect.addEventListener('change', function () {
//             const selectedGroup = this.value;
//             codeSelect.innerHTML = '<option value="">Выбрать код ошибки</option>';
//
//             if (selectedGroup && errorDataGrouped[selectedGroup]) {
//                 errorDataGrouped[selectedGroup].forEach(error => {
//                     const opt = document.createElement('option');
//                     opt.value = error.code;
//                     opt.textContent = `${error.code} — ${error.name}`;
//                     codeSelect.appendChild(opt);
//                 });
//             }
//         });
//     }
// }


    // === ПРИВЯЗКА ОБРАБОТЧИКА К КНОПКЕ "ДОБАВИТЬ" ===
     const addButton = document.getElementById('add-mistake');
     if (addButton) {
         addButton.addEventListener('click', addMistakeBlock);
     } else {
         console.error('Кнопка #add-mistake не найдена в DOM!');
     }

     // === ВОССТАНОВЛЕНИЕ СОХРАНЁННЫХ ДАННЫХ ===
     const saved = localStorage.getItem('stage_7_mistake');
     if (saved) {
         try {
             const data = JSON.parse(saved);

             // Узнаём, сколько блоков было сохранено — обновляем счётчик
             if (data && typeof data === 'object') {
                 mistakeCounter = Object.keys(data).length;
                 for (let i = 1; i <= mistakeCounter; i++) {
                     addMistakeBlock(); // создаём блоки по количеству
                 }

                 // Заполняем данные в каждый блок
                 for (let i = 1; i <= mistakeCounter; i++) {
                     const blockData = data[`block_${i}`];
                     if (!blockData) continue;

                     // Вспомогательная функция для заполнения полей
                     const setVal = (name) => {
                         const el = document.querySelector(`[name="${name}_${i}"]`);
                         if (el && blockData[name + '_' + i] !== undefined) {
                             el.value = blockData[name + '_' + i];
                         }
                     };

                     // Перечисляем все поля для заполнения:
                     setVal('describe_mistake');
                     setVal('fase_of_flight');
                     setVal('mistake_type');
                     setVal('mistake_code_and_describe');
                     setVal('whu_made_mistake');
                     setVal('who_noticed_mistake');
                     setVal('crew_reaction_mistake');
                     setVal('result_of_mistake');
                     setVal('on_treatment_reason');
                     setVal('sucсessful_action');
                     setVal('status_change_code_safety');
                     setVal('who_recognize_status');
                     setVal('mistake_crew_reaction');
                     setVal('status_changing_result');
                 }
             }
         } catch (e) {
             console.error('Ошибка при восстановлении данных этапа 7:', e);
         }
     } else {
         // Если данных нет — создаём первый блок
         addMistakeBlock();
     }
 });


// работа с exel данными

 let errorDataGrouped = null; // Глобально, но в пределах модуля

// // Загружаем данные при загрузке страницы

 document.addEventListener('DOMContentLoaded', async function () {
     try {
         const response = await fetch('/data/error_table.xlsx');
         const arrayBuffer = await response.arrayBuffer();
         const workbook = XLSX.read(arrayBuffer, { type: 'array' });
         const worksheet = workbook.Sheets[workbook.SheetNames[0]];
         const jsonData = XLSX.utils.sheet_to_json(worksheet, { header: 1 });
         const headers = jsonData[0];
         const rows = jsonData.slice(1);
         const errors = rows.map(row => {
             const obj = {};
             headers.forEach((header, index) => {
                 obj[header] = row[index] || '';
             });
             return obj;
         }).filter(row => row.CODE);
         const grouped = {};
         errors.forEach(error => {
             const groupKey = `${error.MAIN_TITLE} | ${error.SUB_TITLE}`.trim();
             if (!grouped[groupKey]) {
                 grouped[groupKey] = [];
             }
             grouped[groupKey].push({
                 code: error.CODE,
                 name: error.ERROR_NAME
             });
         });
         errorDataGrouped = grouped; // Сохраняем для использования в addMistakeBlock
         console.log('✅ Данные ошибок загружены:', errorDataGrouped);
     } catch (err) {
         console.error('❌ Ошибка загрузки Excel:', err);
     }
// Создаём первый блок

});

// document.addEventListener('DOMContentLoaded', async function () {

//     // === 1. Загружаем и парсим Excel ===
//     async function loadErrorData() {
//         try {
//             const response = await fetch('/data/error_table.xlsx');
//             const arrayBuffer = await response.arrayBuffer();
//             const workbook = XLSX.read(arrayBuffer, { type: 'array' });
//             const worksheet = workbook.Sheets[workbook.SheetNames[0]]; // первый лист
//             const jsonData = XLSX.utils.sheet_to_json(worksheet, { header: 1 });
//
//             // Первая строка — заголовки
//             const headers = jsonData[0];
//             const rows = jsonData.slice(1);
//
//             // Преобразуем в массив объектов
//             const errors = rows.map(row => {
//                 const obj = {};
//                 headers.forEach((header, index) => {
//                     obj[header] = row[index] || '';
//                 });
//                 return obj;
//             }).filter(row => row.CODE); // оставляем только строки с кодом
//
//             // Группируем по MAIN_TITLE + SUB_TITLE
//             const grouped = {};
//             errors.forEach(error => {
//                 const groupKey = `${error.MAIN_TITLE} | ${error.SUB_TITLE}`.trim();
//                 if (!grouped[groupKey]) {
//                     grouped[groupKey] = [];
//                 }
//                 grouped[groupKey].push({
//                     code: error.CODE,
//                     name: error.ERROR_NAME
//                 });
//             });
//
//             return { errors, grouped };
//         } catch (err) {
//             console.error('Ошибка загрузки Excel:', err);
//             return { errors: [], grouped: {} };
//         }
//     }
//
//     // === 2. Инициализация селектов ===
//     const typeSelect = document.getElementById('misstake_type');
//     const codeSelect = document.getElementById('misstake_code_and_describe');
//
//     if (!typeSelect || !codeSelect) {
//         console.error('Селекты не найдены!');
//         return;
//     }
//
//     // Загружаем данные
//     const { grouped } = await loadErrorData();
//
////      Заполняем первый селект
//     typeSelect.innerHTML = '<option value="">Выбрать тип ошибки</option>';
//     Object.keys(grouped).forEach(group => {
//         const opt = document.createElement('option');
//         opt.value = group;
//         opt.textContent = group;
//         typeSelect.appendChild(opt);
//     });
//
//     // === 3. Обработчик выбора типа ошибки ===
//     typeSelect.addEventListener('change', function () {
//         const selectedGroup = this.value;
//         codeSelect.innerHTML = '<option value="">Выбрать код ошибки</option>';
//
//         if (selectedGroup && grouped[selectedGroup]) {
//             grouped[selectedGroup].forEach(error => {
//                 const opt = document.createElement('option');
//                 opt.value = error.code;
//                 opt.textContent = `${error.code} — ${error.name}`;
//                 codeSelect.appendChild(opt);
//             });
//         }
//     });
//
// });