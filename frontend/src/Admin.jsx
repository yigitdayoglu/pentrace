import { useEffect, useState } from "react";
import { adminListUsers, adminPatchUser } from "./api.js";

export default function Admin() {
  const [users, setUsers] = useState([]);
  const [error, setError] = useState("");

  async function load() {
    try { setUsers(await adminListUsers()); }
    catch (e) { setError(e.message); }
  }
  useEffect(() => { load(); }, []);

  async function patch(id, field, value) {
    try {
      const updated = await adminPatchUser(id, { [field]: value });
      setUsers((us) => us.map((u) => (u.id === id ? updated : u)));
    } catch (e) { setError(e.message); }
  }

  return (
    <section className="panel">
      <div className="panel-head"><h2>Admin · Kullanici Yonetimi</h2><span className="idx">★</span></div>
      <div className="panel-body">
        {error && <div className="err" style={{ marginBottom: 14 }}>! {error}</div>}
        <table className="admin-table">
          <thead>
            <tr><th>#</th><th>E-posta</th><th>Rol</th><th>Plan</th><th>Kayit</th></tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id}>
                <td className="mono dim">{u.id}</td>
                <td className="mono">{u.email}</td>
                <td>
                  <select value={u.role} onChange={(e) => patch(u.id, "role", e.target.value)}>
                    <option value="user">user</option>
                    <option value="admin">admin</option>
                  </select>
                </td>
                <td>
                  <select value={u.plan} onChange={(e) => patch(u.id, "plan", e.target.value)}>
                    <option value="free">free</option>
                    <option value="pro">pro</option>
                  </select>
                </td>
                <td className="mono dim">{(u.created_at || "").slice(0, 10)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
