import { useState, useEffect, createContext, useContext } from "react";

// ── Config ────────────────────────────────────────────────────────────────────
// URL vazia = chamadas relativas, roteadas pelo proxy do Vite para o gateway
const API = "";

// ── Auth Context ──────────────────────────────────────────────────────────────
const AuthContext = createContext(null);

function useAuth() {
  return useContext(AuthContext);
}

// ── API helpers ───────────────────────────────────────────────────────────────
async function apiFetch(path, options = {}, token = null) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${API}/${path}`, { ...options, headers });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "Erro inesperado");
  return data;
}

// ── Styles ────────────────────────────────────────────────────────────────────
const css = `
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --bg: #f7f8fa;
    --surface: #ffffff;
    --border: #e2e5ea;
    --primary: #2563eb;
    --primary-dark: #1d4ed8;
    --danger: #dc2626;
    --success: #16a34a;
    --text: #111827;
    --muted: #6b7280;
    --radius: 8px;
    --shadow: 0 1px 3px rgba(0,0,0,.08), 0 1px 2px rgba(0,0,0,.04);
  }

  body { font-family: 'Inter', system-ui, sans-serif; background: var(--bg); color: var(--text); font-size: 14px; line-height: 1.5; }

  .app { min-height: 100vh; display: flex; flex-direction: column; }

  /* Navbar */
  nav { background: var(--surface); border-bottom: 1px solid var(--border); padding: 0 24px; height: 56px; display: flex; align-items: center; justify-content: space-between; box-shadow: var(--shadow); }
  nav .brand { font-weight: 700; font-size: 18px; color: var(--primary); letter-spacing: -.5px; }
  nav .nav-right { display: flex; align-items: center; gap: 12px; }
  nav .badge { background: #eff6ff; color: var(--primary); font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 99px; text-transform: capitalize; }
  nav .nav-name { font-weight: 500; color: var(--muted); font-size: 13px; }

  /* Layout */
  .container { max-width: 900px; margin: 0 auto; padding: 32px 16px; flex: 1; }

  /* Cards */
  .card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 24px; box-shadow: var(--shadow); }
  .card + .card { margin-top: 16px; }
  .card-title { font-size: 16px; font-weight: 600; margin-bottom: 16px; }

  /* Auth card */
  .auth-wrap { min-height: 100vh; display: flex; align-items: center; justify-content: center; background: var(--bg); }
  .auth-card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 36px 32px; width: 100%; max-width: 400px; box-shadow: var(--shadow); }
  .auth-title { font-size: 22px; font-weight: 700; color: var(--primary); margin-bottom: 4px; }
  .auth-sub { color: var(--muted); font-size: 13px; margin-bottom: 24px; }

  /* Form */
  .field { margin-bottom: 14px; }
  .field label { display: block; font-size: 12px; font-weight: 600; color: var(--muted); margin-bottom: 4px; text-transform: uppercase; letter-spacing: .4px; }
  .field input, .field select { width: 100%; padding: 9px 12px; border: 1px solid var(--border); border-radius: var(--radius); font-size: 14px; background: var(--bg); color: var(--text); transition: border-color .15s; }
  .field input:focus, .field select:focus { outline: none; border-color: var(--primary); background: #fff; }

  /* Buttons */
  .btn { display: inline-flex; align-items: center; gap: 6px; padding: 9px 16px; border-radius: var(--radius); font-size: 13px; font-weight: 600; cursor: pointer; border: none; transition: background .15s, opacity .15s; }
  .btn:disabled { opacity: .5; cursor: not-allowed; }
  .btn-primary { background: var(--primary); color: #fff; width: 100%; justify-content: center; }
  .btn-primary:hover:not(:disabled) { background: var(--primary-dark); }
  .btn-sm { padding: 5px 12px; font-size: 12px; }
  .btn-danger { background: #fee2e2; color: var(--danger); }
  .btn-danger:hover:not(:disabled) { background: #fecaca; }
  .btn-success { background: #dcfce7; color: var(--success); }
  .btn-success:hover:not(:disabled) { background: #bbf7d0; }
  .btn-outline { background: transparent; color: var(--primary); border: 1px solid var(--primary); }
  .btn-outline:hover:not(:disabled) { background: #eff6ff; }
  .btn-ghost { background: transparent; color: var(--muted); }
  .btn-ghost:hover { color: var(--danger); }

  /* Tabs */
  .tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--border); margin-bottom: 24px; }
  .tab { padding: 10px 16px; font-size: 13px; font-weight: 500; color: var(--muted); cursor: pointer; border: none; background: none; border-bottom: 2px solid transparent; margin-bottom: -1px; transition: color .15s, border-color .15s; }
  .tab.active { color: var(--primary); border-bottom-color: var(--primary); }

  /* Table */
  table { width: 100%; border-collapse: collapse; }
  th { text-align: left; font-size: 11px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: .4px; padding: 8px 12px; border-bottom: 1px solid var(--border); }
  td { padding: 10px 12px; border-bottom: 1px solid var(--border); font-size: 13px; }
  tr:last-child td { border-bottom: none; }
  tr:hover td { background: #f9fafb; }

  /* Status badges */
  .status { display: inline-block; font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 99px; text-transform: capitalize; }
  .status-agendada { background: #eff6ff; color: #2563eb; }
  .status-confirmada { background: #dcfce7; color: #16a34a; }
  .status-concluida { background: #f3f4f6; color: #374151; }
  .status-cancelada { background: #fee2e2; color: #dc2626; }
  .status-falta { background: #fef3c7; color: #d97706; }

  /* Alerts */
  .alert { padding: 10px 14px; border-radius: var(--radius); font-size: 13px; margin-bottom: 14px; }
  .alert-error { background: #fee2e2; color: var(--danger); }
  .alert-success { background: #dcfce7; color: var(--success); }

  /* Grid */
  .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
  .actions { display: flex; gap: 6px; }

  /* Empty */
  .empty { text-align: center; padding: 40px; color: var(--muted); font-size: 13px; }

  /* Section header */
  .section-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
  .section-title { font-size: 18px; font-weight: 700; }

  @media (max-width: 600px) { .grid-2 { grid-template-columns: 1fr; } }
`;

// ── Shared components ─────────────────────────────────────────────────────────
function Alert({ type = "error", msg }) {
  if (!msg) return null;
  return <div className={`alert alert-${type}`}>{msg}</div>;
}

function Spinner() {
  return <div style={{ textAlign: "center", padding: 40, color: "var(--muted)" }}>Carregando...</div>;
}

function StatusBadge({ status }) {
  return <span className={`status status-${status}`}>{status}</span>;
}

// ── Auth screens ──────────────────────────────────────────────────────────────
function LoginScreen({ onLogin, onGoRegister, onGoRecover }) {
  const [form, setForm] = useState({ email: "", senha: "" });
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit() {
    setErr(""); setLoading(true);
    try {
      const data = await apiFetch("auth/login", { method: "POST", body: JSON.stringify(form) });
      onLogin(data);
    } catch (e) { setErr(e.message); }
    finally { setLoading(false); }
  }

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <div className="auth-title">MedMatch</div>
        <div className="auth-sub">Acesse sua conta</div>
        <Alert msg={err} />
        <div className="field"><label>E-mail</label><input type="email" value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} /></div>
        <div className="field"><label>Senha</label><input type="password" value={form.senha} onChange={e => setForm(f => ({ ...f, senha: e.target.value }))} /></div>
        <button className="btn btn-primary" disabled={loading} onClick={submit}>{loading ? "Entrando..." : "Entrar"}</button>
        <div style={{ marginTop: 16, display: "flex", justifyContent: "space-between" }}>
          <button className="btn btn-ghost btn-sm" onClick={onGoRegister}>Criar conta</button>
          <button className="btn btn-ghost btn-sm" onClick={onGoRecover}>Esqueci a senha</button>
        </div>
      </div>
    </div>
  );
}

function RegisterScreen({ onLogin, onGoLogin }) {
  const [form, setForm] = useState({ nome: "", email: "", senha: "", perfil: "paciente" });
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit() {
    setErr(""); setLoading(true);
    try {
      const data = await apiFetch("auth/register", { method: "POST", body: JSON.stringify(form) });
      onLogin(data);
    } catch (e) { setErr(e.message); }
    finally { setLoading(false); }
  }

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <div className="auth-title">MedMatch</div>
        <div className="auth-sub">Criar nova conta</div>
        <Alert msg={err} />
        <div className="field"><label>Nome</label><input value={form.nome} onChange={e => setForm(f => ({ ...f, nome: e.target.value }))} /></div>
        <div className="field"><label>E-mail</label><input type="email" value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} /></div>
        <div className="field"><label>Senha</label><input type="password" value={form.senha} onChange={e => setForm(f => ({ ...f, senha: e.target.value }))} /></div>
        <div className="field">
          <label>Perfil</label>
          <select value={form.perfil} onChange={e => setForm(f => ({ ...f, perfil: e.target.value }))}>
            <option value="paciente">Paciente</option>
            <option value="medico">Medico</option>
            <option value="administrador">Administrador</option>
          </select>
        </div>
        <button className="btn btn-primary" disabled={loading} onClick={submit}>{loading ? "Criando..." : "Criar conta"}</button>
        <div style={{ marginTop: 16 }}>
          <button className="btn btn-ghost btn-sm" onClick={onGoLogin}>Ja tenho conta</button>
        </div>
      </div>
    </div>
  );
}

function RecoverScreen({ onGoLogin }) {
  const [email, setEmail] = useState("");
  const [token, setToken] = useState("");
  const [novaSenha, setNovaSenha] = useState("");
  const [step, setStep] = useState(1);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  async function solicitar() {
    setErr(""); setLoading(true);
    try {
      const data = await apiFetch("recovery/solicitar-reset", { method: "POST", body: JSON.stringify({ email }) });
      setMsg(data.mensagem); setStep(2);
    } catch (e) { setErr(e.message); }
    finally { setLoading(false); }
  }

  async function confirmar() {
    setErr(""); setLoading(true);
    try {
      const data = await apiFetch("recovery/confirmar-reset", { method: "POST", body: JSON.stringify({ token, nova_senha: novaSenha }) });
      setMsg(data.mensagem); setStep(3);
    } catch (e) { setErr(e.message); }
    finally { setLoading(false); }
  }

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <div className="auth-title">MedMatch</div>
        <div className="auth-sub">Recuperar senha</div>
        <Alert msg={err} />
        {msg && <Alert type="success" msg={msg} />}
        {step === 1 && <>
          <div className="field"><label>E-mail cadastrado</label><input type="email" value={email} onChange={e => setEmail(e.target.value)} /></div>
          <button className="btn btn-primary" disabled={loading} onClick={solicitar}>{loading ? "Enviando..." : "Enviar instrucaoes"}</button>
        </>}
        {step === 2 && <>
          <div className="field"><label>Token recebido</label><input value={token} onChange={e => setToken(e.target.value)} /></div>
          <div className="field"><label>Nova senha</label><input type="password" value={novaSenha} onChange={e => setNovaSenha(e.target.value)} /></div>
          <button className="btn btn-primary" disabled={loading} onClick={confirmar}>{loading ? "Salvando..." : "Redefinir senha"}</button>
        </>}
        {step === 3 && <button className="btn btn-primary" onClick={onGoLogin}>Ir para login</button>}
        <div style={{ marginTop: 16 }}>
          <button className="btn btn-ghost btn-sm" onClick={onGoLogin}>Voltar ao login</button>
        </div>
      </div>
    </div>
  );
}

// ── Navbar ────────────────────────────────────────────────────────────────────
function Navbar({ user, onLogout }) {
  return (
    <nav>
      <span className="brand">MedMatch</span>
      <div className="nav-right">
        <span className="nav-name">{user.nome || `ID ${user.usuario_id}`}</span>
        <span className="badge">{user.perfil}</span>
        <button className="btn btn-ghost btn-sm" onClick={onLogout}>Sair</button>
      </div>
    </nav>
  );
}

// ── Paciente Dashboard ────────────────────────────────────────────────────────
function PacienteDashboard({ user }) {
  const [tab, setTab] = useState("agendar");
  const [especialidades, setEspecialidades] = useState([]);
  const [medicos, setMedicos] = useState([]);
  const [horarios, setHorarios] = useState([]);
  const [espSel, setEspSel] = useState("");
  const [medicoSel, setMedicoSel] = useState("");
  const [horarioSel, setHorarioSel] = useState("");
  const [consultas, setConsultas] = useState([]);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    apiFetch("doctors/especialidades").then(setEspecialidades).catch(() => {});
  }, []);

  useEffect(() => {
    if (!espSel) { setMedicos([]); setMedicoSel(""); return; }
    apiFetch(`doctors/medicos?especialidade_id=${espSel}`).then(setMedicos).catch(() => {});
  }, [espSel]);

  useEffect(() => {
    if (!medicoSel) { setHorarios([]); setHorarioSel(""); return; }
    apiFetch(`scheduling/horarios/${medicoSel}`, {}, user.token).then(setHorarios).catch(() => {});
  }, [medicoSel]);

  async function agendar() {
    setErr(""); setMsg(""); setLoading(true);
    try {
      await apiFetch("scheduling/consultas", { method: "POST", body: JSON.stringify({ medico_id: parseInt(medicoSel), horario_id: parseInt(horarioSel) }) }, user.token);
      setMsg("Consulta agendada com sucesso!");
      setHorarioSel(""); carregarConsultas();
    } catch (e) { setErr(e.message); }
    finally { setLoading(false); }
  }

  async function carregarConsultas() {
    // Busca via agenda - paciente ve suas proprias consultas
    try {
      const data = await apiFetch("scheduling/consultas/minhas", {}, user.token);
      setConsultas(data);
    } catch { setConsultas([]); }
  }

  async function cancelar(id) {
    setErr(""); setMsg("");
    try {
      await apiFetch(`scheduling/consultas/${id}`, { method: "DELETE" }, user.token);
      setMsg("Consulta cancelada.");
      carregarConsultas();
    } catch (e) { setErr(e.message); }
  }

  useEffect(() => { if (tab === "consultas") carregarConsultas(); }, [tab]);

  return (
    <div className="container">
      <div className="tabs">
        <button className={`tab ${tab === "agendar" ? "active" : ""}`} onClick={() => setTab("agendar")}>Agendar consulta</button>
        <button className={`tab ${tab === "consultas" ? "active" : ""}`} onClick={() => setTab("consultas")}>Minhas consultas</button>
      </div>

      {tab === "agendar" && (
        <div className="card">
          <div className="card-title">Nova consulta</div>
          <Alert msg={err} />
          <Alert type="success" msg={msg} />
          <div className="grid-2">
            <div className="field">
              <label>Especialidade</label>
              <select value={espSel} onChange={e => setEspSel(e.target.value)}>
                <option value="">Selecione...</option>
                {especialidades.map(e => <option key={e.id} value={e.id}>{e.nome}</option>)}
              </select>
            </div>
            <div className="field">
              <label>Medico</label>
              <select value={medicoSel} onChange={e => setMedicoSel(e.target.value)} disabled={!espSel}>
                <option value="">Selecione...</option>
                {medicos.map(m => <option key={m.id} value={m.id}>{m.nome}</option>)}
              </select>
            </div>
          </div>
          <div className="field">
            <label>Horario disponivel</label>
            <select value={horarioSel} onChange={e => setHorarioSel(e.target.value)} disabled={!medicoSel}>
              <option value="">Selecione...</option>
              {horarios.map(h => <option key={h.id} value={h.id}>{new Date(h.data_hora).toLocaleString("pt-BR")}</option>)}
            </select>
          </div>
          <button className="btn btn-primary" style={{ width: "auto" }} disabled={!horarioSel || loading} onClick={agendar}>
            {loading ? "Agendando..." : "Confirmar agendamento"}
          </button>
        </div>
      )}

      {tab === "consultas" && (
        <div className="card">
          <div className="card-title">Minhas consultas</div>
          <Alert msg={err} />
          <Alert type="success" msg={msg} />
          {consultas.length === 0
            ? <div className="empty">Nenhuma consulta encontrada.</div>
            : <table>
                <thead><tr><th>Data</th><th>Medico</th><th>Especialidade</th><th>Status</th><th></th></tr></thead>
                <tbody>
                  {consultas.map(c => (
                    <tr key={c.id}>
                      <td>{new Date(c.data_hora).toLocaleString("pt-BR")}</td>
                      <td>{c.medico_nome}</td>
                      <td>{c.especialidade}</td>
                      <td><StatusBadge status={c.status} /></td>
                      <td>
                        {c.status === "agendada" &&
                          <button className="btn btn-danger btn-sm" onClick={() => cancelar(c.id)}>Cancelar</button>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
          }
        </div>
      )}
    </div>
  );
}

// ── Medico Dashboard ──────────────────────────────────────────────────────────
function MedicoDashboard({ user }) {
  const [tab, setTab] = useState("agenda");

  return (
    <div className="container">
      <div className="tabs">
        <button className={`tab ${tab === "agenda" ? "active" : ""}`} onClick={() => setTab("agenda")}>Minha agenda</button>
        <button className={`tab ${tab === "horarios" ? "active" : ""}`} onClick={() => setTab("horarios")}>Gerenciar horarios</button>
      </div>
      {tab === "agenda"   && <MedicoAgenda user={user} />}
      {tab === "horarios" && <MedicoHorarios user={user} />}
    </div>
  );
}

function MedicoAgenda({ user }) {
  const [agenda, setAgenda] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");

  async function carregar() {
    setLoading(true);
    try {
      const data = await apiFetch("scheduling/agenda", {}, user.token);
      setAgenda(data);
    } catch (e) { setErr(e.message); }
    finally { setLoading(false); }
  }

  async function atualizarStatus(id, status) {
    setErr(""); setMsg("");
    try {
      await apiFetch(`scheduling/consultas/${id}/status`, { method: "PATCH", body: JSON.stringify({ status }) }, user.token);
      setMsg(`Status atualizado para "${status}".`);
      carregar();
    } catch (e) { setErr(e.message); }
  }

  useEffect(() => { carregar(); }, []);

  return <>
    <div className="section-header">
      <div className="section-title">Agenda</div>
      <button className="btn btn-outline btn-sm" onClick={carregar}>Atualizar</button>
    </div>
    <Alert msg={err} />
    <Alert type="success" msg={msg} />
    <div className="card">
      {loading ? <Spinner /> : agenda.length === 0
        ? <div className="empty">Nenhuma consulta na agenda.</div>
        : <table>
            <thead><tr><th>Data / Hora</th><th>Paciente</th><th>Contato</th><th>Status</th><th>Acoes</th></tr></thead>
            <tbody>
              {agenda.map(c => (
                <tr key={c.id}>
                  <td>{new Date(c.data_hora).toLocaleString("pt-BR")}</td>
                  <td>{c.paciente_nome}</td>
                  <td>{c.paciente_email}</td>
                  <td><StatusBadge status={c.status} /></td>
                  <td>
                    <div className="actions">
                      {c.status === "agendada" && <>
                        <button className="btn btn-success btn-sm" onClick={() => atualizarStatus(c.id, "confirmada")}>Confirmar</button>
                        <button className="btn btn-sm" style={{ background: "#f3f4f6" }} onClick={() => atualizarStatus(c.id, "falta")}>Falta</button>
                      </>}
                      {c.status === "confirmada" &&
                        <button className="btn btn-sm" style={{ background: "#f3f4f6" }} onClick={() => atualizarStatus(c.id, "concluida")}>Concluir</button>}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
      }
    </div>
  </>;
}

function MedicoHorarios({ user }) {
  const [horarios, setHorarios] = useState([]);
  const [dataHora, setDataHora] = useState("");
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [loading, setLoading] = useState(false);

  async function carregar() {
    try {
      const data = await apiFetch(`scheduling/horarios/${user.usuario_id}`, {}, user.token);
      setHorarios(data);
    } catch { setHorarios([]); }
  }

  async function adicionar() {
    setErr(""); setMsg(""); setLoading(true);
    try {
      await apiFetch("scheduling/horarios", {
        method: "POST",
        body: JSON.stringify({ data_hora: dataHora })
      }, user.token);
      setMsg("Horario adicionado.");
      setDataHora("");
      carregar();
    } catch (e) { setErr(e.message); }
    finally { setLoading(false); }
  }

  async function remover(id) {
    setErr(""); setMsg("");
    try {
      await apiFetch(`scheduling/horarios/${id}`, { method: "DELETE" }, user.token);
      setMsg("Horario removido.");
      carregar();
    } catch (e) { setErr(e.message); }
  }

  useEffect(() => { carregar(); }, []);

  return <>
    <Alert msg={err} />
    <Alert type="success" msg={msg} />
    <div className="card" style={{ marginBottom: 16 }}>
      <div className="card-title">Adicionar horario disponivel</div>
      <div style={{ display: "flex", gap: 10, alignItems: "flex-end" }}>
        <div className="field" style={{ flex: 1, marginBottom: 0 }}>
          <label>Data e hora</label>
          <input type="datetime-local" value={dataHora} onChange={e => setDataHora(e.target.value)} />
        </div>
        <button className="btn btn-primary" style={{ width: "auto" }} disabled={!dataHora || loading} onClick={adicionar}>
          {loading ? "Adicionando..." : "Adicionar"}
        </button>
      </div>
    </div>

    <div className="card">
      <div className="card-title">Meus horarios cadastrados</div>
      {horarios.length === 0
        ? <div className="empty">Nenhum horario cadastrado.</div>
        : <table>
            <thead><tr><th>Data / Hora</th><th>Situacao</th><th></th></tr></thead>
            <tbody>
              {horarios.map(h => (
                <tr key={h.id}>
                  <td>{new Date(h.data_hora).toLocaleString("pt-BR")}</td>
                  <td>{h.disponivel
                    ? <span className="status status-confirmada">Disponivel</span>
                    : <span className="status status-agendada">Agendado</span>}
                  </td>
                  <td>
                    {h.disponivel &&
                      <button className="btn btn-danger btn-sm" onClick={() => remover(h.id)}>Remover</button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
      }
    </div>
  </>;
}

// ── Admin Dashboard ───────────────────────────────────────────────────────────
function AdminDashboard({ user }) {
  const [tab, setTab] = useState("medicos");

  return (
    <div className="container">
      <div className="tabs">
        <button className={`tab ${tab === "medicos" ? "active" : ""}`} onClick={() => setTab("medicos")}>Medicos</button>
        <button className={`tab ${tab === "especialidades" ? "active" : ""}`} onClick={() => setTab("especialidades")}>Especialidades</button>
      </div>
      {tab === "medicos" && <AdminMedicos user={user} />}
      {tab === "especialidades" && <AdminEspecialidades user={user} />}
    </div>
  );
}

function AdminMedicos({ user }) {
  const [medicos, setMedicos] = useState([]);
  const [especialidades, setEspecialidades] = useState([]);
  const [form, setForm] = useState({ nome: "", email_profissional: "", telefone_profissional: "", especialidade_id: "", crm: "" });
  const [editId, setEditId] = useState(null);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [loading, setLoading] = useState(false);

  async function carregar() {
    const [m, e] = await Promise.all([
      apiFetch("doctors/medicos", {}, user.token).catch(() => []),
      apiFetch("doctors/especialidades", {}, user.token).catch(() => []),
    ]);
    setMedicos(m); setEspecialidades(e);
  }

  useEffect(() => { carregar(); }, []);

  function iniciarEdicao(m) {
    setEditId(m.id);
    setForm({ nome: m.nome, email_profissional: m.email_profissional, telefone_profissional: m.telefone_profissional || "", especialidade_id: String(m.especialidade_id || ""), crm: m.crm || "" });
  }

  function cancelarEdicao() { setEditId(null); setForm({ nome: "", email_profissional: "", telefone_profissional: "", especialidade_id: "", crm: "" }); }

  async function salvar() {
    setErr(""); setMsg(""); setLoading(true);
    try {
      const body = { ...form, especialidade_id: parseInt(form.especialidade_id) };
      if (editId) {
        await apiFetch(`doctors/medicos/${editId}`, { method: "PUT", body: JSON.stringify(body) }, user.token);
        setMsg("Medico atualizado.");
      } else {
        await apiFetch("doctors/medicos", { method: "POST", body: JSON.stringify(body) }, user.token);
        setMsg("Medico cadastrado.");
      }
      cancelarEdicao(); carregar();
    } catch (e) { setErr(e.message); }
    finally { setLoading(false); }
  }

  async function remover(id) {
    if (!confirm("Remover este medico?")) return;
    setErr(""); setMsg("");
    try {
      await apiFetch(`doctors/medicos/${id}`, { method: "DELETE" }, user.token);
      setMsg("Medico removido."); carregar();
    } catch (e) { setErr(e.message); }
  }

  return <>
    <Alert msg={err} />
    <Alert type="success" msg={msg} />
    <div className="card" style={{ marginBottom: 16 }}>
      <div className="card-title">{editId ? "Editar medico" : "Novo medico"}</div>
      <div className="grid-2">
        <div className="field"><label>Nome</label><input value={form.nome} onChange={e => setForm(f => ({ ...f, nome: e.target.value }))} /></div>
        <div className="field"><label>CRM</label><input value={form.crm} onChange={e => setForm(f => ({ ...f, crm: e.target.value }))} /></div>
        <div className="field"><label>E-mail profissional</label><input value={form.email_profissional} onChange={e => setForm(f => ({ ...f, email_profissional: e.target.value }))} /></div>
        <div className="field"><label>Telefone</label><input value={form.telefone_profissional} onChange={e => setForm(f => ({ ...f, telefone_profissional: e.target.value }))} /></div>
        <div className="field">
          <label>Especialidade</label>
          <select value={form.especialidade_id} onChange={e => setForm(f => ({ ...f, especialidade_id: e.target.value }))}>
            <option value="">Selecione...</option>
            {especialidades.map(e => <option key={e.id} value={e.id}>{e.nome}</option>)}
          </select>
        </div>
      </div>
      <div className="actions">
        <button className="btn btn-primary" style={{ width: "auto" }} disabled={loading} onClick={salvar}>{loading ? "Salvando..." : editId ? "Salvar alteracaoes" : "Cadastrar medico"}</button>
        {editId && <button className="btn btn-outline" onClick={cancelarEdicao}>Cancelar</button>}
      </div>
    </div>

    <div className="card">
      <div className="card-title">Medicos cadastrados</div>
      {medicos.length === 0
        ? <div className="empty">Nenhum medico cadastrado.</div>
        : <table>
            <thead><tr><th>Nome</th><th>CRM</th><th>Especialidade</th><th>E-mail</th><th></th></tr></thead>
            <tbody>
              {medicos.map(m => (
                <tr key={m.id}>
                  <td>{m.nome}</td>
                  <td>{m.crm}</td>
                  <td>{m.especialidade}</td>
                  <td>{m.email_profissional}</td>
                  <td>
                    <div className="actions">
                      <button className="btn btn-outline btn-sm" onClick={() => iniciarEdicao(m)}>Editar</button>
                      <button className="btn btn-danger btn-sm" onClick={() => remover(m.id)}>Remover</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
      }
    </div>
  </>;
}

function AdminEspecialidades({ user }) {
  const [especialidades, setEspecialidades] = useState([]);
  const [nome, setNome] = useState("");
  const [editId, setEditId] = useState(null);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");

  async function carregar() {
    apiFetch("doctors/especialidades").then(setEspecialidades).catch(() => {});
  }

  useEffect(() => { carregar(); }, []);

  function iniciarEdicao(e) { setEditId(e.id); setNome(e.nome); }
  function cancelar() { setEditId(null); setNome(""); }

  async function salvar() {
    setErr(""); setMsg("");
    try {
      if (editId) {
        await apiFetch(`doctors/especialidades/${editId}`, { method: "PUT", body: JSON.stringify({ nome }) }, user.token);
        setMsg("Especialidade atualizada.");
      } else {
        await apiFetch("doctors/especialidades", { method: "POST", body: JSON.stringify({ nome }) }, user.token);
        setMsg("Especialidade criada.");
      }
      cancelar(); carregar();
    } catch (e) { setErr(e.message); }
  }

  async function remover(id) {
    if (!confirm("Remover esta especialidade?")) return;
    try {
      await apiFetch(`doctors/especialidades/${id}`, { method: "DELETE" }, user.token);
      setMsg("Especialidade removida."); carregar();
    } catch (e) { setErr(e.message); }
  }

  return <>
    <Alert msg={err} />
    <Alert type="success" msg={msg} />
    <div className="card" style={{ marginBottom: 16 }}>
      <div className="card-title">{editId ? "Editar especialidade" : "Nova especialidade"}</div>
      <div style={{ display: "flex", gap: 10, alignItems: "flex-end" }}>
        <div className="field" style={{ flex: 1, marginBottom: 0 }}>
          <label>Nome</label>
          <input value={nome} onChange={e => setNome(e.target.value)} placeholder="Ex: Cardiologia" />
        </div>
        <button className="btn btn-primary" style={{ width: "auto" }} onClick={salvar}>{editId ? "Salvar" : "Adicionar"}</button>
        {editId && <button className="btn btn-outline" onClick={cancelar}>Cancelar</button>}
      </div>
    </div>

    <div className="card">
      <div className="card-title">Especialidades cadastradas</div>
      {especialidades.length === 0
        ? <div className="empty">Nenhuma especialidade cadastrada.</div>
        : <table>
            <thead><tr><th>Nome</th><th></th></tr></thead>
            <tbody>
              {especialidades.map(e => (
                <tr key={e.id}>
                  <td>{e.nome}</td>
                  <td>
                    <div className="actions">
                      <button className="btn btn-outline btn-sm" onClick={() => iniciarEdicao(e)}>Editar</button>
                      <button className="btn btn-danger btn-sm" onClick={() => remover(e.id)}>Remover</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
      }
    </div>
  </>;
}

// ── App root ──────────────────────────────────────────────────────────────────
export default function App() {
  const [user, setUser] = useState(() => {
    try { return JSON.parse(sessionStorage.getItem("medmatch_user")); } catch { return null; }
  });
  const [screen, setScreen] = useState("login"); // login | register | recover

  function handleLogin(data) {
    const u = { ...data, token: data.access_token };
    sessionStorage.setItem("medmatch_user", JSON.stringify(u));
    setUser(u);
  }

  function handleLogout() {
    sessionStorage.removeItem("medmatch_user");
    setUser(null); setScreen("login");
  }

  return (
    <>
      <style>{css}</style>
      <div className="app">
        {!user ? (
          screen === "login"    ? <LoginScreen onLogin={handleLogin} onGoRegister={() => setScreen("register")} onGoRecover={() => setScreen("recover")} /> :
          screen === "register" ? <RegisterScreen onLogin={handleLogin} onGoLogin={() => setScreen("login")} /> :
                                  <RecoverScreen onGoLogin={() => setScreen("login")} />
        ) : (
          <>
            <Navbar user={user} onLogout={handleLogout} />
            {user.perfil === "paciente"       && <PacienteDashboard user={user} />}
            {user.perfil === "medico"         && <MedicoDashboard user={user} />}
            {user.perfil === "administrador"  && <AdminDashboard user={user} />}
          </>
        )}
      </div>
    </>
  );
}
