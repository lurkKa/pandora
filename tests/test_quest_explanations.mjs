import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';
const source=readFileSync(new URL('../index.html',import.meta.url),'utf8');
const cardSource=source.slice(source.indexOf('        function buildMethodBadges('),source.indexOf('        function htmlToElement('));
const editorSource=source.slice(source.indexOf("        let explanationLastValue = ''"),source.indexOf('        // ==================== CODE EXECUTION (SERVER-VERIFIED)'));
function harness() {
    const elements=new Map();
    function element(id) {
        if (!elements.has(id)) {
            const classes=new Set(); const events=new Map();
            elements.set(id,{value:'',innerText:'',disabled:false,events,
                classList:{add:x=>classes.add(x),remove:x=>classes.delete(x),contains:x=>classes.has(x),toggle:(x,force)=>force?classes.add(x):classes.delete(x)},
                addEventListener:(name,handler)=>events.set(name,handler),focus(){}});
        }
        return elements.get(id);
    }
    const events=[]; const requests=[];
    const context=vm.createContext({
        document:{getElementById:element},
        taskTypingTelemetry:{record:(...event)=>events.push(event)},
        taskEditorChangedChars:(a,b)=>a===b?0:Math.max(1,b.length),
        currentTask:{id:'py-old',completed:true,explanation_required:true},
        tasks:[{id:'py-old',completed:true,explanation_required:true}],
        currentFilter:'python',homeworkByTask:{},featuredTask:null,
        runCodeInFlight:false,refreshQuestBoard(){},loadTaskStatus:async()=>{},currentUser:{xp:0,level:1},updateXPDisplay(){},
        finalizeTaskTypingTelemetry:async()=>({typing_session_id:'session',typing_receipt:'receipt'}),
        API_URL:'https://pandora.test',authToken:'token',safeJson:JSON.stringify,
        fetch:async(url,options)=>{requests.push({url,options});return {ok:true,json:async()=>({status:'explanation_completed',xp_earned:0})};}
    });
    vm.runInContext(cardSource+editorSource,context);
    return {context,element,events,requests};
}

test('half and full cards retain distinct states without a progress bar',()=>{
    const {context}=harness();
    const task={id:'py-old',category:'python',title:'Сумма',tier:'D',completed:true,explanation_required:true};
    context.task=task;context.ids=new Set(['py-old']);
    const half=vm.runInContext('renderQuestCard(task,ids,{python:"🐍"})',context);
    const halfSignature=vm.runInContext('getQuestCardSignature(task,ids)',context);
    assert.match(half,/partially-completed/);assert.match(half,/50% · Добавь объяснение/);assert.doesNotMatch(half,/quest-completion-track/);
    task.explanation_required=false;
    const full=vm.runInContext('renderQuestCard(task,ids,{python:"🐍"})',context);
    assert.doesNotMatch(full,/partially-completed/);assert.match(full,/100% · Выполнено/);assert.doesNotMatch(full,/quest-completion-track/);
    assert.notEqual(vm.runInContext('getQuestCardSignature(task,ids)',context),halfSignature);
});

test('paste, drop and alternate browser insertion are blocked even with code paste permission',()=>{
    const {element,events}=harness();
    for (const name of ['paste','drop','beforeinput']) {
        let blocked=false;
        element('solution-explanation').events.get(name)({inputType:'insertFromPaste',isTrusted:true,preventDefault(){blocked=true;}});
        assert.equal(blocked,true);
    }
    assert.equal(events.length,3);assert.equal(events[0][0],'blocked');
});

test('explanation typing contributes to telemetry and synthetic replacements stay untrusted',()=>{
    const {element,events,context}=harness();
    const editor=element('solution-explanation');
    editor.events.get('beforeinput')({inputType:'insertText',isTrusted:true});
    editor.value='а';editor.events.get('input')({isTrusted:true});
    assert.deepEqual(events[0],['insert',1,true]);
    editor.value='подставленный текст';editor.events.get('input')({isTrusted:false});
    assert.equal(events[1][0],'programmatic');assert.equal(events[1][2],false);
    editor.value='ещё один текст';vm.runInContext('reconcileExplanationTelemetry()',context);
    assert.equal(events[2][0],'programmatic');
});

test('restoring a half completion uses the explanation endpoint and changes only completion display',async()=>{
    const {context,element,requests}=harness();
    element('solution-explanation').value='Функция solve принимает два числа и складывает аргументы, после чего возвращает сумму как результат.';
    await vm.runInContext('saveTaskExplanation()',context);
    assert.equal(requests.length,1);assert.match(requests[0].url,/\/py-old\/explanation$/);
    const body=JSON.parse(requests[0].options.body);
    assert.equal(body.explanation,element('solution-explanation').value);
    assert.equal(body.typing_receipt,'receipt');assert.equal(body.code,undefined);
    assert.equal(context.currentTask.explanation_required,false);
    assert.equal(context.tasks[0].completion_percent,100);
    assert.match(element('output-console').innerText,/100%/);
});

test('short explanations accept ten characters while shorter text stays in the editor',async()=>{
    const {context,element,requests}=harness();
    element('solution-explanation').value='Сумма a+b';
    await vm.runInContext('saveTaskExplanation()',context);
    assert.equal(requests.length,0);
    assert.match(element('output-console').innerText,/от 10 символов/);
    element('solution-explanation').value='Суммирую a';
    await vm.runInContext('saveTaskExplanation()',context);
    assert.equal(requests.length,1);
});

test('accepted code-only response preserves the half badge and offers explanation later',()=>{
    const {context,element}=harness();
    vm.runInContext('markExplanationComplete({explanation_required:true,completion_percent:50})',context);
    assert.equal(context.currentTask.explanation_required,true);
    assert.equal(context.currentTask.completion_percent,50);
    assert.equal(context.tasks[0].explanation_required,true);
    assert.equal(element('save-explanation-btn').classList.contains('hidden'),false);
});

test('explanation completion updates the XP balance and reports the remaining reward',async()=>{
    const {context,element}=harness();
    context.fetch=async()=>({ok:true,json:async()=>({status:'explanation_completed',xp_earned:13,stars_earned:.5,xp:120,level:3,explanation_required:false})});
    element('solution-explanation').value='Функция solve принимает два числа и складывает аргументы, после чего возвращает сумму как результат.';
    await vm.runInContext('saveTaskExplanation()',context);
    assert.equal(context.currentUser.xp,120);
    assert.equal(context.currentUser.level,3);
    assert.match(element('output-console').innerText,/13 XP/);
    assert.match(element('output-console').innerText,/0,5/);
});

test('admin review displays explanation as text and hides the panel for Scratch',()=>{
    const admin=readFileSync(new URL('../admin.html',import.meta.url),'utf8');
    const review=admin.slice(admin.indexOf('        function showReviewExplanation('),admin.indexOf('        function closeCodeModal('));
    const elements=new Map([
        ['code-explanation-wrap',{style:{display:''}}],
        ['code-explanation',{textContent:''}]
    ]);
    const context=vm.createContext({document:{getElementById:id=>elements.get(id)}});
    vm.runInContext(review,context);
    context.text='<img src=x onerror=alert(1)> Объяснение ученика';
    vm.runInContext('showReviewExplanation(text,"python")',context);
    assert.equal(elements.get('code-explanation').textContent,context.text);
    assert.equal(elements.get('code-explanation-wrap').style.display,'block');
    vm.runInContext('showReviewExplanation("","frontend")',context);
    assert.match(elements.get('code-explanation').textContent,/50%/);
    vm.runInContext('showReviewExplanation("","scratch")',context);
    assert.equal(elements.get('code-explanation-wrap').style.display,'none');
});

test('grading modal shows code and explanation and previews the reduced reward',()=>{
    const source=readFileSync(new URL('../admin.html',import.meta.url),'utf8');
    const section=source.slice(source.indexOf('        let currentReviewMaxXP = 0;'),source.indexOf('        async function submitReview('));
    const elements=new Map();
    const get=id=>{
        if(!elements.has(id)) elements.set(id,{value:0,innerText:'',textContent:'',style:{},classList:{add(){},remove(){}}});
        return elements.get(id);
    };
    const context=vm.createContext({document:{getElementById:get}});
    vm.runInContext(section,context);
    vm.runInContext('openReviewModal(1,"Тест",25,"","Условие",{category:"python",code:"print(1)",explanation:""})',context);
    assert.equal(get('review-work-code').textContent,'print(1)');
    assert.equal(get('review-work-wrap').style.display,'block');
    assert.equal(get('review-calculated-xp').innerText,12);
    vm.runInContext('openReviewModal(1,"Тест",25,"","Условие",{category:"python",code:"print(1)",explanation:"Мой текст"})',context);
    assert.equal(get('review-work-explanation').textContent,'Мой текст');
    assert.equal(get('review-calculated-xp').innerText,25);
    vm.runInContext('openReviewModal(2,"Scratch",25,"","Условие",{category:"scratch"})',context);
    assert.equal(get('review-work-wrap').style.display,'none');
    assert.equal(get('review-calculated-xp').innerText,25);
});
