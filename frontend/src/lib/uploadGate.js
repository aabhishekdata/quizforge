export const UPLOAD_UNLOCK_CODE = 'Ilovequizforge'
export const UPLOAD_UNLOCK_KEY = 'qf_upload_unlocked'
export const UPLOAD_UNLOCK_EVENT = 'qf-upload-unlocked'

export function isUploadUnlocked() {
  return localStorage.getItem(UPLOAD_UNLOCK_KEY) === '1'
}

export function unlockUpload() {
  localStorage.setItem(UPLOAD_UNLOCK_KEY, '1')
  window.dispatchEvent(new Event(UPLOAD_UNLOCK_EVENT))
}
