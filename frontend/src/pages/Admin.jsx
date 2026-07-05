import { useEffect, useState } from 'react'
import { api } from '../lib/api'

export default function Admin() {
  const [codes, setCodes] = useState([])
  const [resetCodes, setResetCodes] = useState([])
  const [groups, setGroups] = useState([])
  const [groupName, setGroupName] = useState('')
  const [resetUsername, setResetUsername] = useState('')
  const [memberDrafts, setMemberDrafts] = useState({})
  const [msg, setMsg] = useState('')

  const loadInvites = () => api.get('/api/admin/invites').then(setCodes)
  const loadResets = () => api.get('/api/admin/password-resets').then(setResetCodes)
  const loadGroups = () => api.get('/api/admin/groups').then(setGroups)
  const load = () => { loadInvites(); loadResets(); loadGroups() }
  useEffect(load, [])

  const createInvite = async () => { await api.post('/api/admin/invites'); loadInvites() }
  const createReset = async () => {
    const username = resetUsername.trim()
    if (!username) return
    setMsg('')
    try {
      await api.post('/api/admin/password-resets', { username })
      setResetUsername('')
      loadResets()
    } catch (e) { setMsg(e.message) }
  }
  const createGroup = async () => {
    setMsg('')
    try {
      await api.post('/api/admin/groups', { name: groupName.trim() })
      setGroupName('')
      loadGroups()
    } catch (e) { setMsg(e.message) }
  }
  const addMember = async (groupId) => {
    const username = (memberDrafts[groupId] || '').trim()
    if (!username) return
    setMsg('')
    try {
      const updated = await api.post(`/api/admin/groups/${groupId}/members`, { username })
      setGroups(groups.map(g => (g.id === groupId ? updated : g)))
      setMemberDrafts({ ...memberDrafts, [groupId]: '' })
    } catch (e) { setMsg(e.message) }
  }
  const removeMember = async (groupId, username) => {
    const updated = await api.del(`/api/admin/groups/${groupId}/members/${encodeURIComponent(username)}`)
    setGroups(groups.map(g => (g.id === groupId ? updated : g)))
  }

  return (
    <div className="max-w-4xl mx-auto space-y-10">
      <section>
        <h1 className="font-display font-extrabold text-3xl mb-6">Invite codes</h1>
        <button onClick={createInvite}
                className="rounded-md bg-marker text-ink font-display font-bold px-4 py-2 mb-6">
          + Generate code
        </button>
        <div className="space-y-2">
          {codes.map(c => (
            <div key={c.code} className="flex items-center justify-between rounded-md bg-board px-4 py-3">
              <span className="font-num tracking-widest">{c.code}</span>
              <span className="text-sm text-mist">
                {c.used_by ? `used by ${c.used_by}` : 'unused'}
              </span>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2 className="font-display font-extrabold text-2xl mb-2">Password resets</h2>
        <p className="text-sm text-mist mb-4">Generate a one-time reset code for a user. Codes expire after 24 hours.</p>
        <div className="flex gap-2 mb-5">
          <input value={resetUsername} onChange={e => setResetUsername(e.target.value)}
                 onKeyDown={e => e.key === 'Enter' && createReset()}
                 placeholder="Username"
                 className="flex-1 rounded-md bg-board px-3 py-2 text-sm placeholder:text-mist focus:outline-none focus:ring-2 focus:ring-marker" />
          <button onClick={createReset}
                  className="rounded-md bg-marker text-ink font-display font-bold px-4 py-2">
            Generate reset
          </button>
        </div>
        <div className="space-y-2">
          {resetCodes.map(c => (
            <div key={`${c.code}-${c.username}`} className="flex items-center justify-between rounded-md bg-board px-4 py-3 gap-4">
              <span className="font-num tracking-widest">{c.code}</span>
              <span className="text-sm text-mist">
                {c.used_at ? `used by ${c.username}` : `for ${c.username}`}
              </span>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2 className="font-display font-extrabold text-2xl mb-2">Groups</h2>
        <p className="text-sm text-mist mb-4">Create study groups and add users by username.</p>
        <div className="flex gap-2 mb-5">
          <input value={groupName} onChange={e => setGroupName(e.target.value)}
                 onKeyDown={e => e.key === 'Enter' && createGroup()}
                 placeholder="Group name"
                 className="flex-1 rounded-md bg-board px-3 py-2 text-sm placeholder:text-mist focus:outline-none focus:ring-2 focus:ring-marker" />
          <button onClick={createGroup}
                  className="rounded-md bg-marker text-ink font-display font-bold px-4 py-2">
            Create group
          </button>
        </div>
        {msg && <p className="text-sm text-redline mb-3">{msg}</p>}
        <div className="grid gap-4">
          {groups.map(g => (
            <div key={g.id} className="index-card p-4">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="font-display font-bold text-lg">{g.name}</p>
                  <p className="text-xs text-ink/50 font-num">{g.members.length} members</p>
                </div>
              </div>
              <div className="flex gap-2 mt-4">
                <input value={memberDrafts[g.id] || ''}
                       onChange={e => setMemberDrafts({ ...memberDrafts, [g.id]: e.target.value })}
                       onKeyDown={e => e.key === 'Enter' && addMember(g.id)}
                       placeholder="Username"
                       className="flex-1 rounded-md border border-rule px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-marker" />
                <button onClick={() => addMember(g.id)}
                        className="rounded-md bg-ink text-marker font-display font-bold px-3 py-2 text-sm">
                  Add
                </button>
              </div>
              {g.members.length > 0 && (
                <div className="flex flex-wrap gap-2 mt-4">
                  {g.members.map(username => (
                    <span key={username}
                          className="inline-flex items-center gap-2 rounded-full bg-board/10 border border-rule px-3 py-1 text-sm">
                      {username}
                      <button onClick={() => removeMember(g.id, username)}
                              className="font-bold text-redline"
                              title={`Remove ${username}`}>
                        x
                      </button>
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
