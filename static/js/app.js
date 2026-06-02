// Utilities for Toast
let toastTimeout;
function showToast(message) {
    const toast = document.getElementById('save-toast');
    if(!toast) return;
    toast.textContent = message;
    toast.classList.remove('opacity-0');
    
    clearTimeout(toastTimeout);
    toastTimeout = setTimeout(() => {
        toast.classList.add('opacity-0');
    }, 2000);
}

// --- Route Selector Logic ---
async function initRouteSelector() {
    const routeSelect = document.getElementById('filter-route');
    if (!routeSelect) return;
    
    try {
        const res = await fetch('/api/rotas');
        const rotas = await res.json();
        
        if (rotas && rotas.length > 0) {
            routeSelect.innerHTML = rotas.map(r => `<option value="${r}">${r}</option>`).join('');
            
            let activeRoute = localStorage.getItem('activeRoute');
            if (!activeRoute || !rotas.includes(activeRoute)) {
                activeRoute = rotas[0];
                localStorage.setItem('activeRoute', activeRoute);
            }
            routeSelect.value = activeRoute;
        } else {
            routeSelect.innerHTML = '<option value="">Nenhuma rota carregada</option>';
        }
    } catch (e) {
        console.error("Erro ao carregar rotas:", e);
        routeSelect.innerHTML = '<option value="">Erro ao carregar rotas</option>';
    }
}

function changeRoute(routeVal) {
    if (!routeVal) return;
    localStorage.setItem('activeRoute', routeVal);
    
    if (document.getElementById('client-list')) {
        if (typeof resetOptimizeState === 'function') resetOptimizeState();
        loadClientes();
    }
    if (document.getElementById('metas-progress-cards')) {
        loadMetasOperationalPage();
    }
}

// --- Dashboard Logic ---
async function loadDashboard() {
    const container = document.getElementById('dashboard-cards');
    if(!container) return;

    container.innerHTML = `
        <div class="animate-pulse flex flex-col space-y-4">
            <div class="h-24 bg-gray-200 rounded-xl"></div>
            <div class="h-24 bg-gray-200 rounded-xl"></div>
        </div>
    `;

    try {
        const activeRoute = localStorage.getItem('activeRoute') || '';
        const res = await fetch(`/api/dashboard?rota=${activeRoute}`);
        const data = await res.json();
        
        if (data.error) {
            container.innerHTML = `<div class="p-4 bg-yellow-50 text-yellow-800 rounded-lg text-sm">${data.error} Vá para Ajustes para configurar.</div>`;
            return;
        }

        const metas = data.metas;
        const real = data.realizado;

        let html = '';
        
        // Sempre Juntos Card
        const sjPct = real.sempre_juntos_pct;
        const sjMeta = metas.sempre_juntos_pct;
        const sjColor = sjPct >= sjMeta ? 'bg-green-500' : 'bg-brand';
        
        html += createProgressCard('Sempre Juntos', `${sjPct}%`, `${sjMeta}%`, (sjPct/sjMeta)*100, sjColor);

        // Cervejas
        const cvColor = real.cerveja_total >= metas.cerveja_total ? 'bg-green-500' : 'bg-yellow-500';
        html += createProgressCard('Cervejas', real.cerveja_total, metas.cerveja_total, (real.cerveja_total/metas.cerveja_total)*100, cvColor);

        // Others (simplified list)
        html += `
        <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-4">
            <h4 class="text-sm font-semibold text-gray-700 mb-3">Outras Metas</h4>
            <div class="space-y-3">
                ${createMiniBar('600ml', real.cerveja_600ml, metas.cerveja_600ml)}
                ${createMiniBar('Long Neck', real.cerveja_ln, metas.cerveja_ln)}
                ${createMiniBar('Lata', real.cerveja_lata, metas.cerveja_lata)}
                ${createMiniBar('ARTD', real.drinks, metas.drinks)}
                ${createMiniBar('Monster', real.monster, metas.monster)}
                ${createMiniBar('Perfetti', real.perfetti, metas.perfetti)}
                ${createMiniBar('Alcoólicos', real.campari, metas.campari)}
            </div>
        </div>
        `;

        container.innerHTML = html;
    } catch(e) {
        container.innerHTML = `<div class="p-4 bg-red-50 text-red-800 rounded-lg text-sm">Erro ao carregar dashboard.</div>`;
    }
}

function createProgressCard(title, current, target, pct, colorClass, borderClass = '') {
    if(pct > 100) pct = 100;
    if(isNaN(pct) || !isFinite(pct)) pct = 0;
    
    return `
    <div class="bg-white rounded-xl shadow-sm border border-gray-100 ${borderClass} p-4 relative overflow-hidden hover:shadow-md transition-all duration-200">
        <div class="flex justify-between items-end mb-2 relative z-10">
            <div>
                <h3 class="text-gray-400 text-[10px] font-bold uppercase tracking-wider">${title}</h3>
                <div class="text-2xl font-bold text-gray-800 mt-1">${current} <span class="text-xs font-normal text-gray-400">/ ${target}</span></div>
            </div>
            <div class="text-xs font-bold ${colorClass.replace('bg-', 'text-')}">${Math.round(pct)}%</div>
        </div>
        <div class="w-full bg-gray-100 h-2 rounded-full relative z-10 overflow-hidden">
            <div class="${colorClass} h-2 rounded-full progress-fill" style="width: ${pct}%"></div>
        </div>
    </div>`;
}

function createMiniBar(title, current, target) {
    let pct = target > 0 ? (current / target) * 100 : 0;
    if(pct > 100) pct = 100;
    const color = pct >= 100 ? 'bg-green-500' : 'bg-brand-light';
    
    return `
    <div>
        <div class="flex justify-between text-xs mb-1">
            <span class="text-gray-600 font-medium">${title}</span>
            <span class="text-gray-500">${current}/${target}</span>
        </div>
        <div class="w-full bg-gray-100 h-1.5 rounded-full">
            <div class="${color} h-1.5 rounded-full" style="width: ${pct}%"></div>
        </div>
    </div>`;
}

// Caching variables for instant local search
let allLoadedClientes = [];

async function loadClientes() {
    const list = document.getElementById('client-list');
    if(!list) return;

    list.innerHTML = `<li class="p-4 text-center bg-white rounded-xl border border-gray-100 text-gray-400 text-sm animate-pulse">Carregando clientes...</li>`;
    const countSpan = document.getElementById('client-count');
    if (countSpan) countSpan.textContent = "...";

    const meta = document.getElementById('filter-meta') ? document.getElementById('filter-meta').value : 'todos';
    
    const activeRoute = localStorage.getItem('activeRoute') || '';
    let url = `/api/clientes?rota=${activeRoute}&`;
    if(currentDia) url += `dia=${currentDia}&`;
    if(currentSemana) url += `semana=${currentSemana}&`;
    if(meta) url += `status_meta=${meta}&`;
    
    if (typeof isOptimized !== 'undefined' && isOptimized && userCoords) {
        url += `user_lat=${userCoords.lat}&user_lng=${userCoords.lng}&`;
    }

    try {
        const res = await fetch(url);
        allLoadedClientes = await res.json();
        
        // Reset search input on a fresh load of the day/week/status
        const searchInput = document.getElementById('search-input');
        if (searchInput) {
            searchInput.value = '';
        }
        
        renderClientesList(allLoadedClientes);
    } catch(e) {
        list.innerHTML = `<li class="p-4 text-center text-red-500 text-sm">Erro ao carregar clientes.</li>`;
        const countSpan = document.getElementById('client-count');
        if (countSpan) countSpan.textContent = "0";
    }
}

function renderClientesList(clientes) {
    const list = document.getElementById('client-list');
    if(!list) return;
    
    const countSpan = document.getElementById('client-count');
    if (countSpan) {
        countSpan.textContent = clientes.length;
    }
    
    if(clientes.length === 0) {
        list.innerHTML = `<li class="p-4 text-center text-gray-500 text-sm">Nenhum cliente encontrado.</li>`;
        return;
    }

    list.innerHTML = clientes.map(c => {
        const p = c.positivados || [];
        let badgesHtml = '';
        
        const baseMetas = [
            { key: 'Sempre Juntos', label: 'Sempre Juntos', classes: 'bg-red-100 text-red-800' },
            { key: 'Cervejas', label: 'Cervejas', classes: 'bg-amber-100 text-amber-800' },
            { key: 'Drinks', label: 'Drinks', classes: 'bg-blue-100 text-blue-800' },
            { key: 'Monster', label: 'Monster', classes: 'bg-green-100 text-green-800' },
            { key: 'Perfetti', label: 'Perfetti', classes: 'bg-pink-100 text-pink-800' },
            { key: 'Alcoólicos', label: 'Alcoólicos', classes: 'bg-orange-100 text-orange-800' }
        ];
        
        baseMetas.forEach(meta => {
            if (p.includes(meta.key)) {
                badgesHtml += `<span class="text-[9px] font-bold px-1.5 py-0.5 rounded ${meta.classes} shrink-0">${meta.label}</span>`;
            }
        });
        
        const baseKeys = baseMetas.map(m => m.key);
        p.forEach(name => {
            if (!baseKeys.includes(name)) {
                badgesHtml += `<span class="text-[9px] font-bold px-1.5 py-0.5 rounded bg-purple-100 text-purple-800 shrink-0 truncate max-w-[80px]">${name}</span>`;
            }
        });
        
        const badgesContainer = badgesHtml ? `<div class="flex flex-wrap gap-1 mt-1.5 mb-0.5">${badgesHtml}</div>` : '';
        
        return `
        <li>
            <a href="/cliente/${c.cod_cliente}" class="block p-4 bg-white rounded-xl border border-gray-100 shadow-sm hover:border-brand-light/30 hover:shadow-md tactile-card">
                <div class="flex justify-between items-start">
                    <div class="pr-2 flex-1 min-w-0">
                        <h4 class="font-bold text-gray-800 text-sm leading-snug mb-1 truncate">${c.razao_social}</h4>
                        ${badgesContainer}
                        <p class="text-[11px] text-gray-400 truncate mt-2 w-full flex items-center gap-1">
                            <i class="ph ph-map-pin text-gray-400"></i>
                            ${c.endereco || ''}, ${c.bairro || ''} - ${c.cidade || ''}
                        </p>
                    </div>
                    <div class="flex flex-col items-end shrink-0 ml-2">
                        <span class="text-[9px] font-bold px-2 py-0.5 rounded bg-red-50 text-brand mb-1.5 uppercase tracking-wide">${c.novo_dia} (${c.nova_semana})</span>
                        <span class="text-[10px] text-gray-400 font-mono">#${c.cod_cliente}</span>
                    </div>
                </div>
            </a>
        </li>
        `;
    }).join('');
}

function filterClientesLocal() {
    const searchInput = document.getElementById('search-input');
    if (!searchInput) return;
    
    const query = searchInput.value.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim();
    
    if (!query) {
        renderClientesList(allLoadedClientes);
        return;
    }
    
    const filtered = allLoadedClientes.filter(c => {
        const name = (c.razao_social || '').toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
        const code = (c.cod_cliente || '').toLowerCase();
        return name.includes(query) || code.includes(query);
    });
    
    renderClientesList(filtered);
}

async function loadDynamicFilters() {
    const select = document.getElementById('filter-meta');
    if(!select) return;
    
    select.innerHTML = `
        <option value="todos">Todos os Clientes</option>
        <option value="cervejas">Compraram Cervejas</option>
        <option value="drinks">Compraram Drinks</option>
        <option value="sempre_juntos">Compraram Sempre Juntos</option>
    `;
    
    try {
        const res = await fetch('/api/produtos');
        const data = await res.json();
        data.forEach(p => {
            if(p.nome_produto !== "Cervejas" && p.nome_produto !== "Drinks" && p.nome_produto !== "Sempre Juntos") {
                const opt = document.createElement('option');
                opt.value = p.id;
                opt.textContent = `Compraram ${p.nome_produto}`;
                select.appendChild(opt);
            }
        });
    } catch(e) {
        console.error("Erro ao carregar filtros dinâmicos:", e);
    }
}

// --- Config Logic ---
let selectedFileRoutes = [];

async function scanFileRoutes(file) {
    const routeContainer = document.getElementById('route-selection-container');
    const routeSelect = document.getElementById('route-select');
    const msg = document.getElementById('upload-message');
    const btnText = document.getElementById('upload-text');
    const spinner = document.getElementById('upload-spinner');
    
    if(!routeContainer || !routeSelect) return;
    
    // Reset state
    routeContainer.classList.add('hidden');
    routeSelect.innerHTML = '<option value="">-- Selecione uma Rota --</option>';
    msg.classList.add('hidden');
    
    btnText.textContent = "Analisando planilha...";
    spinner.classList.remove('hidden');
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        const res = await fetch('/api/scan-routes', {
            method: 'POST',
            body: formData
        });
        const data = await res.json();
        
        if (res.ok && data.routes && data.routes.length > 0) {
            selectedFileRoutes = data.routes;
            data.routes.forEach(route => {
                const opt = document.createElement('option');
                opt.value = route;
                opt.textContent = route;
                routeSelect.appendChild(opt);
            });
            routeContainer.classList.remove('hidden');
            msg.textContent = `Encontradas ${data.routes.length} rotas. Escolha uma abaixo.`;
            msg.className = "mt-3 text-sm text-center text-green-600 font-semibold";
            msg.classList.remove('hidden');
        } else {
            msg.textContent = data.message || "Não foi possível extrair rotas desta planilha. Verifique a coluna 'Nova Rota'.";
            msg.className = "mt-3 text-sm text-center text-red-600 font-semibold";
            msg.classList.remove('hidden');
        }
    } catch(err) {
        console.error("Erro ao analisar rotas:", err);
        alert("Erro ao detectar rotas: " + err.message);
        msg.textContent = "Erro de conexão ao analisar rotas: " + err.message;
        msg.className = "mt-3 text-sm text-center text-red-600 font-semibold";
        msg.classList.remove('hidden');
    } finally {
        btnText.textContent = "Importar Rota";
        spinner.classList.add('hidden');
    }
}

async function handleUpload(e) {
    e.preventDefault();
    const fileInput = document.getElementById('csv-file');
    const routeSelect = document.getElementById('route-select');
    if(fileInput.files.length === 0) return;
    
    const selectedRoute = routeSelect.value;
    if (!selectedRoute) {
        alert("Por favor, selecione uma rota no dropdown antes de importar!");
        return;
    }

    const btnText = document.getElementById('upload-text');
    const spinner = document.getElementById('upload-spinner');
    const msg = document.getElementById('upload-message');
    
    btnText.textContent = `Importando ${selectedRoute}...`;
    spinner.classList.remove('hidden');
    msg.classList.add('hidden');

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);
    formData.append('rota', selectedRoute);

    try {
        const res = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });
        const data = await res.json();
        
        msg.textContent = data.message;
        msg.className = res.ok ? "mt-3 text-sm text-center text-green-600 font-bold" : "mt-3 text-sm text-center text-red-600 font-bold";
    } catch(err) {
        msg.textContent = "Erro na conexão.";
        msg.className = "mt-3 text-sm text-center text-red-600";
    } finally {
        msg.classList.remove('hidden');
        btnText.textContent = "Importar Rota";
        spinner.classList.add('hidden');
    }
}

async function handleMetasSave(e) {
    e.preventDefault();
    const formData = new FormData(e.target);
    const btn = e.target.querySelector('button[type="submit"]');
    const originalText = btn.textContent;
    btn.textContent = "Salvando...";

    try {
        await fetch('/api/metas', {
            method: 'POST',
            body: formData
        });
        alert('Metas salvas com sucesso!');
    } catch(err) {
        alert('Erro ao salvar metas.');
    } finally {
        btn.textContent = originalText;
    }
}

async function loadMetas() {
    const form = document.getElementById('metas-form');
    if(!form) return;

    try {
        const res = await fetch('/api/metas');
        const data = await res.json();
        if(Object.keys(data).length > 0) {
            for(const key in data) {
                const input = form.elements[key];
                if(input) input.value = data[key];
            }
        }
    } catch(e) {}
}

// --- Cliente Profile Logic ---
async function loadClienteData(cod) {
    try {
        const res = await fetch(`/api/cliente/${cod}`);
        const data = await res.json();
        
        const c = data.cliente;
        document.getElementById('cli-nome').textContent = c.razao_social;
        document.getElementById('cli-end').textContent = `${c.endereco || ''}, ${c.bairro || ''} - ${c.cidade || ''}`;
        document.getElementById('cli-rota').textContent = `${c.novo_dia} (${c.nova_semana})`;
        document.getElementById('cli-canal').textContent = c.canal_resumido;
        document.getElementById('cli-class').textContent = c.classificacao;

        // Sempre Juntos Rule
        if(canaisSempreJuntos.includes(c.canal_resumido)) {
            document.getElementById('container-sempre-juntos').classList.remove('hidden');
        }

        // Fill checkboxes
        const p = data.positivacao;
        
        // Find main products meta IDs
        const prodRes = await fetch('/api/produtos');
        const products = await prodRes.json();
        
        // Fill static checklist checkboxes (Sempre Juntos, Cervejas, Alcoólicos, Drinks, Monster, Perfetti, and sub-items)
        document.querySelectorAll('#checklist-container input[type="checkbox"]').forEach(chk => {
            if (chk.id.startsWith('chk-prod_')) return;
            
            const key = chk.id.replace('chk-', '');
            if (p[key] !== undefined) {
                chk.checked = p[key] === true;
                // If this is a category checklist master container and it's checked, expand its sublist
                if (p[key] === true && (key === 'cervejas' || key === 'alcoolicos' || key === 'drinks')) {
                    const subContainer = document.getElementById(`sublist-${key}`);
                    const chevron = document.getElementById(`chevron-${key}`);
                    if (subContainer) subContainer.classList.add('expanded');
                    if (chevron) chevron.classList.add('rotate-180');
                }
            } else {
                chk.checked = false;
            }
        });
        
        // Dynamic Launches Checklist rendering
        const launchesContainer = document.getElementById('dynamic-launches-checklist');
        if (launchesContainer) {
            launchesContainer.innerHTML = '';
            
            // Filter out core products
            const dynamicLaunches = products.filter(prod => 
                prod.nome_produto !== "Cervejas" && 
                prod.nome_produto !== "Drinks" && 
                prod.nome_produto !== "Sempre Juntos" &&
                prod.nome_produto !== "Monster" &&
                prod.nome_produto !== "Perfetti" &&
                prod.nome_produto !== "Alcoólicos" &&
                prod.nome_produto !== "Campari"
            );
            
            if (dynamicLaunches.length > 0) {
                const divider = document.createElement('div');
                divider.className = "my-4 border-t border-gray-100";
                launchesContainer.appendChild(divider);
                
                const title = document.createElement('h4');
                title.className = "text-xs font-bold text-gray-400 uppercase tracking-wider mb-3";
                title.textContent = "Lançamentos e Foco";
                launchesContainer.appendChild(title);
                
                dynamicLaunches.forEach(prod => {
                    const isChecked = p[String(prod.id)] === true || p[`prod_${prod.id}`] === true;
                    const lbl = document.createElement('label');
                    lbl.className = "custom-checkbox-container";
                    lbl.innerHTML = `
                        ${prod.nome_produto}
                        <input type="checkbox" id="chk-prod_${prod.id}" ${isChecked ? 'checked' : ''} onchange="saveCheck('prod_${prod.id}')">
                        <span class="checkmark"></span>
                    `;
                    launchesContainer.appendChild(lbl);
                });
            }
        }

    } catch(e) {
        console.error(e);
        document.getElementById('cli-nome').textContent = "Erro ao carregar";
    }
}

async function saveCheck(field) {
    const chk = document.getElementById(`chk-${field}`);
    const val = chk ? chk.checked : false;
    
    showToast('Salvando...');

    try {
        await fetch(`/api/positivacao/${codCliente}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({[field]: val})
        });
        showToast('Salvo!');
    } catch(e) {
        showToast('Erro ao salvar');
    }
}

// --- Metas Page Dynamic Logic ---
async function loadMetasOperationalPage() {
    const cardsContainer = document.getElementById('metas-progress-cards');
    const launchesList = document.getElementById('launches-list');
    
    if(!cardsContainer || !launchesList) return;

    cardsContainer.innerHTML = `
        <div class="animate-pulse flex flex-col space-y-4">
            <div class="h-24 bg-gray-200 rounded-xl"></div>
            <div class="h-24 bg-gray-200 rounded-xl"></div>
        </div>
    `;
    launchesList.innerHTML = `<li class="p-3 text-center text-sm text-gray-400 animate-pulse">Carregando...</li>`;
    
    try {
        const activeRoute = localStorage.getItem('activeRoute') || '';
        const res = await fetch(`/api/dashboard?rota=${activeRoute}`);
        const data = await res.json();
        
        if (data.error) {
            cardsContainer.innerHTML = `<div class="p-4 bg-yellow-50 text-yellow-800 rounded-lg text-sm">${data.error} Vá para Ajustes para configurar.</div>`;
            return;
        }
        
        const metas = data.metas;
        const real = data.realizado;
        const launches = data.launches;
        
        let html = '';
        
        // --- 6 METAS PRINCIPAIS (Always visible at the top) ---
        
        // 1. Sempre Juntos Card
        const sjPct = real.sempre_juntos_pct;
        const sjMeta = metas.sempre_juntos_pct;
        const sjColor = sjPct >= sjMeta ? 'bg-green-500' : 'bg-brand';
        html += createProgressCard('Sempre Juntos', `${sjPct}%`, `${sjMeta}%`, (sjPct/sjMeta)*100, sjColor, 'border-l-4 border-l-red-500');
        
        // 2. Cervejas Card
        const cvColor = real.cerveja_total >= metas.cerveja_total ? 'bg-green-500' : 'bg-yellow-500';
        html += createProgressCard('Cervejas', real.cerveja_total, metas.cerveja_total, (real.cerveja_total/metas.cerveja_total)*100, cvColor, 'border-l-4 border-l-amber-500');
        
        // 3. Drinks Card
        const drinksVal = real.drinks || 0;
        const drinksMeta = metas.drinks || 10;
        const drinksColor = drinksVal >= drinksMeta ? 'bg-green-500' : 'bg-blue-500';
        html += createProgressCard('Drinks', drinksVal, drinksMeta, (drinksVal/drinksMeta)*100, drinksColor, 'border-l-4 border-l-blue-500');
        
        // 4. Monster Card
        const monsterVal = real.monster || 0;
        const monsterMeta = metas.monster || 10;
        const monsterColor = monsterVal >= monsterMeta ? 'bg-green-500' : 'bg-purple-500';
        html += createProgressCard('Monster', monsterVal, monsterMeta, (monsterVal/monsterMeta)*100, monsterColor, 'border-l-4 border-l-green-500');
        
        // 5. Perfetti Card
        const perfettiVal = real.perfetti || 0;
        const perfettiMeta = metas.perfetti || 10;
        const perfettiColor = perfettiVal >= perfettiMeta ? 'bg-green-500' : 'bg-pink-500';
        html += createProgressCard('Perfetti', perfettiVal, perfettiMeta, (perfettiVal/perfettiMeta)*100, perfettiColor, 'border-l-4 border-l-pink-500');
        
        // 6. Alcoólicos Card
        const campariVal = real.campari || 0;
        const campariMeta = metas.campari || 10;
        const campariColor = campariVal >= campariMeta ? 'bg-green-500' : 'bg-orange-500';
        html += createProgressCard('Alcoólicos', campariVal, campariMeta, (campariVal/campariMeta)*100, campariColor, 'border-l-4 border-l-orange-500');
        
        // --- SUBSEÇÕES OPCIONAIS E COLAPSÁVEIS (Closed by default) ---
        
        // A. Quebras de Cerveja Collapsible Section
        html += `
        <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-5 mt-4">
            <button class="w-full flex justify-between items-center text-left focus:outline-none" onclick="toggleAccordion('quebras-cerveja-accordion', 'quebras-chevron')">
                <h3 class="font-semibold text-gray-700 flex items-center">
                    <i class="ph ph-beer-bottle text-xl mr-2 text-brand"></i>
                    Quebras de Cerveja (Sub-itens)
                </h3>
                <i id="quebras-chevron" class="ph ph-caret-down text-gray-400 text-lg transition-transform duration-200"></i>
            </button>
            <div id="quebras-cerveja-accordion" class="hidden mt-4 pt-4 border-t border-gray-100 space-y-4">
                ${createMiniBar('Cerveja 600ml', real.cerveja_600ml || 0, metas.cerveja_600ml || 10)}
                ${createMiniBar('Cerveja Long Neck', real.cerveja_ln || 0, metas.cerveja_ln || 10)}
                ${createMiniBar('Cerveja Lata', real.cerveja_lata || 0, metas.cerveja_lata || 10)}
            </div>
        </div>
        `;
        
        // B. Lançamentos e Produtos Foco Collapsible Section
        if (launches && launches.length > 0) {
            html += `
            <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-5 mt-4">
                <button class="w-full flex justify-between items-center text-left focus:outline-none" onclick="toggleAccordion('launches-accordion', 'launches-chevron')">
                    <h3 class="font-semibold text-gray-700 flex items-center">
                        <i class="ph ph-rocket text-xl mr-2 text-brand"></i>
                        Lançamentos e Produtos Foco
                    </h3>
                    <i id="launches-chevron" class="ph ph-caret-down text-gray-400 text-lg transition-transform duration-200"></i>
                </button>
                <div id="launches-accordion" class="hidden mt-4 pt-4 border-t border-gray-100 space-y-4">
            `;
            launches.forEach(lp => {
                const pct = lp.meta > 0 ? (lp.realizado / lp.meta) * 100 : 0;
                const color = pct >= 100 ? 'bg-green-500' : 'bg-brand-light';
                html += `
                <div>
                    <div class="flex justify-between text-xs font-semibold mb-1">
                        <span class="text-gray-700">${lp.nome_produto}</span>
                        <span class="text-gray-500">${lp.realizado} / ${lp.meta}</span>
                    </div>
                    <div class="w-full bg-gray-100 h-2.5 rounded-full overflow-hidden">
                        <div class="${color} h-2.5 rounded-full progress-fill" style="width: ${pct}%"></div>
                    </div>
                </div>
                `;
            });
            html += `</div></div>`;
        } else {
            html += `
            <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-5 mt-4">
                <button class="w-full flex justify-between items-center text-left focus:outline-none" onclick="toggleAccordion('launches-accordion', 'launches-chevron')">
                    <h3 class="font-semibold text-gray-700 flex items-center">
                        <i class="ph ph-rocket text-xl mr-2 text-brand"></i>
                        Lançamentos e Produtos Foco
                    </h3>
                    <i id="launches-chevron" class="ph ph-caret-down text-gray-400 text-lg transition-transform duration-200"></i>
                </button>
                <div id="launches-accordion" class="hidden mt-4 pt-4 border-t border-gray-100 text-center text-sm text-gray-500">
                    Nenhum lançamento adicional cadastrado.
                </div>
            </div>
            `;
        }
        
        cardsContainer.innerHTML = html;
        
        // 5. Render Launches List for management
        if (launches && launches.length > 0) {
            launchesList.innerHTML = launches.map(lp => `
                <li class="p-3 bg-white flex justify-between items-center text-sm border-b border-gray-50 last:border-0">
                    <div class="flex flex-col">
                        <span class="font-medium text-gray-700">${lp.nome_produto}</span>
                        <span class="text-[10px] text-gray-400 font-semibold">Meta de Positivação: ${lp.meta} clientes</span>
                    </div>
                    <span class="text-xs px-2 py-0.5 rounded bg-green-50 text-green-600 font-semibold uppercase">Ativo</span>
                </li>
            `).join('');
        } else {
            launchesList.innerHTML = `<li class="p-4 text-center text-sm text-gray-500">Nenhum lançamento cadastrado</li>`;
        }
        
    } catch(err) {
        cardsContainer.innerHTML = `<div class="p-4 bg-red-50 text-red-800 rounded-lg text-sm">Erro ao carregar metas dinâmicas.</div>`;
    }
}

// Global Accordion Handler for safe references
function toggleAccordion(id, chevronId) {
    const accordion = document.getElementById(id);
    const chevron = document.getElementById(chevronId);
    if (!accordion || !chevron) return;
    
    if (accordion.classList.contains('hidden')) {
        accordion.classList.remove('hidden');
        chevron.classList.add('rotate-180');
    } else {
        accordion.classList.add('hidden');
        chevron.classList.remove('rotate-180');
    }
}

async function handleAddProduct(e) {
    e.preventDefault();
    const inputName = document.getElementById('new-product-name');
    const inputMeta = document.getElementById('new-product-meta');
    if(!inputName || !inputMeta) return;

    const name = inputName.value.trim();
    const targetMeta = inputMeta.value.trim();
    if(!name || !targetMeta) return;
    
    const btn = e.target.querySelector('button[type="submit"]');
    const origText = btn.innerHTML;
    btn.innerHTML = '<i class="ph ph-spinner animate-spin"></i>';
    
    const formData = new FormData();
    formData.append('nome_produto', name);
    formData.append('meta_quantidade', targetMeta);
    
    try {
        const res = await fetch('/api/produtos', {
            method: 'POST',
            body: formData
        });
        const data = await res.json();
        
        if (res.ok) {
            inputName.value = '';
            inputMeta.value = '';
            showToast('Produto Foco cadastrado!');
            loadMetasOperationalPage();
        } else {
            alert(data.message || "Erro ao cadastrar.");
        }
    } catch(err) {
        alert("Erro de conexão ao adicionar produto.");
    } finally {
        btn.innerHTML = origText;
    }
}
