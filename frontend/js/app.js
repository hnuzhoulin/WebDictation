// 创建 Vue 应用
const app = Vue.createApp({
    data() {
        return {
            // 课程数据
            grades: [],
            lessons: [],
            selectedGrade: '',
            selectedLesson: '',
            
            // TTS设置
            ttsEngine: 'edge-tts',
            voices: [],
            selectedVoice: '',
            rate: 1.0,
            
            // 播放控制
            playMode: 'sequence',
            repeatCount: 1,
            repeatInterval: 3,
            showWord: false,  // 默认不显示，将从后端获取配置
            
            // 听写状态
            isDictating: false,
            currentWord: '',
            words: [],
            currentIndex: 0,
            
            // 系统状态
            status: null,
            sessionId: null,
            
            // 错误信息
            error: null,
            
            // 加载状态
            loading: {
                grades: false,
                lessons: false,
                voices: false
            },
            
            // 添加自动播放状态
            autoPlay: {
                timer: null,
                currentRepeatCount: 0
            },
            
            // MP3 生成状态
            isGenerating: false,
            mp3Url: null,
            
            // 音频状态
            audioState: {
                currentAudio: null,
                audioQueue: [],
                isPlaying: false,
                currentRepeatCount: 0
            },
            
            // 浏览器环境
            browser: {
                isWechat: /MicroMessenger/i.test(navigator.userAgent),
                audioContext: null
            },
            
            // 缓存状态
            cacheStatus: {
                isChecking: false,
                progress: 0,
                total: 0
            }
        }
    },
    
    computed: {
        // 过滤后的语音列表
        filteredVoices() {
            if (this.ttsEngine === 'edge-tts') {
                // 只显示简体中文和英文的语音
                return this.voices.filter(voice => 
                    voice.locale === 'zh-CN' || 
                    voice.locale === 'en-US' ||
                    voice.locale === 'en-GB'
                ).map(voice => ({
                    ...voice,
                    displayName: `${voice.name} (${voice.gender === 'Female' ? '女声' : '男声'}, ${voice.locale === 'zh-CN' ? '中文' : '英文'})`
                }))
            }
            return this.voices
        }
    },
    
    methods: {
        // 显示错误信息
        showError(message) {
            this.error = message
            console.error(message)
            setTimeout(() => {
                this.error = null
            }, 5000)  // 显示5秒
        },
        
        // 初始化
        async init() {
            this.sessionId = 'session_' + Math.random().toString(36).substr(2, 9)
            
            // 初始化音频上下文（针对微信浏览器）
            if (this.browser.isWechat) {
                try {
                    const AudioContext = window.AudioContext || window.webkitAudioContext
                    this.browser.audioContext = new AudioContext()
                } catch (e) {
                    console.error('创建音频上下文失败:', e)
                }
            }
            
            await this.loadConfig()
            await this.loadGrades()
            await this.loadVoices()
            this.startStatusPolling()
        },
        
        // 加载配置
        async loadConfig() {
            try {
                const response = await axios.get('/api/tts/config')
                if (response.data.success) {
                    this.showWord = response.data.data.showWord
                }
            } catch (error) {
                console.error('加载配置失败:', error)
            }
        },
        
        // 加载年级列表
        async loadGrades() {
            if (this.loading.grades) return
            this.loading.grades = true
            
            try {
                const response = await axios.get('/api/lessons')
                console.log('年级数据:', response.data)  // 调试输出
                
                if (response.data.success) {
                    // 提取并去重年级
                    const grades = [...new Set(response.data.data.map(item => item.grade))]
                    console.log('处理后的年级列表:', grades)  // 调试输出
                    
                    if (grades.length > 0) {
                        this.grades = grades
                        // 不自动选择年级，让用户手动选择
                        this.selectedGrade = ''
                    } else {
                        this.showError('没有找到任何年级数据')
                    }
                } else {
                    this.showError('加载年级失败: ' + response.data.message)
                }
            } catch (error) {
                this.showError('加载年级失败: ' + (error.response?.data?.detail || error.message))
            } finally {
                this.loading.grades = false
            }
        },
        
        // 加载课时列表
        async loadLessons() {
            if (!this.selectedGrade) {
                this.lessons = []
                this.selectedLesson = ''
                return
            }
            
            if (this.loading.lessons) return
            this.loading.lessons = true
            
            try {
                const response = await axios.get('/api/lessons')
                console.log('课时数据:', response.data)  // 调试输出
                
                if (response.data.success) {
                    // 过滤当前年级的课时
                    const gradeLessons = response.data.data
                        .filter(item => item.grade === this.selectedGrade)
                    const lessons = gradeLessons.map(item => item.lesson)
                    console.log('处理后的课时列表:', lessons)  // 调试输出
                    
                    if (lessons.length > 0) {
                        this.lessons = lessons
                        // 不自动选择课时，让用户手动选择
                        this.selectedLesson = ''
                    } else {
                        this.showError(`没有找到${this.selectedGrade}的课时数据`)
                    }
                } else {
                    this.showError('加载课时失败: ' + response.data.message)
                }
            } catch (error) {
                this.showError('加载课时失败: ' + (error.response?.data?.detail || error.message))
            } finally {
                this.loading.lessons = false
            }
        },
        
        // 加载语音列表
        async loadVoices() {
            if (this.loading.voices) return
            this.loading.voices = true
            
            try {
                if (this.ttsEngine === 'web-speech') {
                    // 使用Web Speech API获取语音列表
                    if ('speechSynthesis' in window) {
                        // 等待语音列表加载
                        await new Promise((resolve) => {
                            if (speechSynthesis.getVoices().length) {
                                resolve()
                            } else {
                                speechSynthesis.onvoiceschanged = resolve
                            }
                        })
                        
                        // 获取语音列表
                        const voices = speechSynthesis.getVoices()
                        this.voices = voices.map(voice => ({
                            name: voice.name,
                            locale: voice.lang,
                            gender: voice.name.toLowerCase().includes('female') ? 'Female' : 'Male'
                        }))
                        
                        if (this.filteredVoices.length > 0) {
                            // 默认选择第一个中文语音
                            const defaultVoice = this.filteredVoices.find(v => 
                                v.locale.startsWith('zh-')
                            )
                            this.selectedVoice = defaultVoice ? defaultVoice.name : this.filteredVoices[0].name
                        }
                    } else {
                        this.showError('您的浏览器不支持 Web Speech API')
                    }
                } else {
                    // 使用后端TTS服务获取语音列表
                    const response = await axios.get(`/api/tts/voices?engine=${this.ttsEngine}`)
                    console.log('语音数据:', response.data)  // 调试输出
                    
                    if (response.data.success) {
                        this.voices = response.data.data
                        if (this.filteredVoices.length > 0) {
                            // 默认选择第一个中文女声
                            const defaultVoice = this.filteredVoices.find(v => 
                                v.locale === 'zh-CN' && v.gender === 'Female'
                            )
                            this.selectedVoice = defaultVoice ? defaultVoice.name : this.filteredVoices[0].name
                        } else {
                            this.showError('没有找到可用的语音')
                        }
                    } else {
                        this.showError('加载语音失败: ' + response.data.message)
                    }
                }
            } catch (error) {
                this.showError('加载语音失败: ' + (error.response?.data?.detail || error.message))
            } finally {
                this.loading.voices = false
            }
        },
        
        // 开始听写
        async startDictation() {
            if (!this.selectedGrade || !this.selectedLesson) {
                this.showError('请先选择年级和课时')
                return
            }
            
            try {
                // 加载单词列表
                const response = await axios.get(
                    `/api/lessons/${encodeURIComponent(this.selectedGrade)}/${encodeURIComponent(this.selectedLesson)}/words`
                )
                
                if (response.data.success) {
                    let words = response.data.data.words
                    if (this.playMode === 'random') {
                        // 随机打乱单词顺序
                        words = words
                            .map(value => ({ value, sort: Math.random() }))
                            .sort((a, b) => a.sort - b.sort)
                            .map(({ value }) => value)
                    }
                    
                    this.words = words
                    
                    // 检查缓存状态
                    const cacheResult = await this.checkCache(words)
                    
                    if (cacheResult) {
                        // 所有缓存就绪，开始听写
                        this.currentIndex = 0
                        this.isDictating = true
                        this.playCurrentWord()
                    }
                } else {
                    this.showError('加载单词失败: ' + response.data.message)
                }
            } catch (error) {
                this.showError('加载单词失败: ' + (error.response?.data?.detail || error.message))
            }
        },
        
        // 使用AudioContext播放音频（针对微信浏览器）
        async playAudioWithContext(audioData) {
            try {
                const audioContext = this.browser.audioContext
                if (!audioContext) throw new Error('音频上下文未初始化')

                // 将音频数据转换为ArrayBuffer
                const arrayBuffer = await audioData.arrayBuffer()
                
                // 解码音频数据
                const audioBuffer = await audioContext.decodeAudioData(arrayBuffer)
                
                // 创建音频源
                const source = audioContext.createBufferSource()
                source.buffer = audioBuffer
                source.connect(audioContext.destination)
                
                // 记录开始时间
                const startTime = audioContext.currentTime
                
                // 开始播放
                source.start(0)
                
                // 返回Promise，在播放结束时resolve
                return new Promise((resolve) => {
                    source.onended = resolve
                    // 如果播放时间超过音频长度，也认为播放结束
                    setTimeout(resolve, audioBuffer.duration * 1000 + 100)
                })
            } catch (error) {
                console.error('音频播放失败:', error)
                throw error
            }
        },
        
        // 预加载音频
        async preloadAudio(text) {
            try {
                const headers = { 'X-Session-ID': this.sessionId }
                const response = await axios.post('/api/tts', {
                    text: text,
                    engine: this.ttsEngine,
                    voice: this.selectedVoice,
                    rate: this.rate
                }, {
                    headers,
                    responseType: 'blob'
                })
                
                if (this.browser.isWechat) {
                    // 微信浏览器直接返回音频数据
                    return response.data
                } else {
                    // 其他浏览器使用Audio对象
                    const audio = new Audio()
                    audio.src = URL.createObjectURL(response.data)
                    
                    // 等待音频加载完成
                    await new Promise((resolve, reject) => {
                        audio.oncanplaythrough = resolve
                        audio.onerror = reject
                        audio.load()
                    })
                    
                    return audio
                }
            } catch (error) {
                console.error('预加载音频失败:', error)
                throw error
            }
        },
        
        // 播放当前单词
        async playCurrentWord() {
            if (!this.isDictating || this.currentIndex >= this.words.length) {
                return
            }
            
            this.currentWord = this.words[this.currentIndex]
            
            // 使用Web Speech API
            if (this.ttsEngine === 'web-speech') {
                this.playWithWebSpeech()
                return
            }
            
            try {
                // 停止当前播放
                if (this.audioState.currentAudio) {
                    if (this.browser.isWechat) {
                        // 微信浏览器不需要特殊处理停止
                    } else {
                        this.audioState.currentAudio.pause()
                        this.audioState.currentAudio.src = ''
                    }
                }
                
                // 重置状态
                this.audioState.currentRepeatCount = 0
                this.audioState.isPlaying = true
                
                // 预加载当前音频
                const audio = await this.preloadAudio(this.currentWord)
                this.audioState.currentAudio = audio
                
                // 预加载下一个单词（如果有）
                if (this.currentIndex < this.words.length - 1) {
                    const nextWord = this.words[this.currentIndex + 1]
                    this.preloadAudio(nextWord).then(nextAudio => {
                        this.audioState.audioQueue = [nextAudio]
                    }).catch(console.error)
                }
                
                // 播放音频
                if (this.browser.isWechat) {
                    // 微信浏览器使用AudioContext播放
                    for (let i = 0; i < this.repeatCount; i++) {
                        if (!this.audioState.isPlaying) break
                        
                        if (i > 0) {
                            // 重复播放之间的间隔
                            await new Promise(resolve => setTimeout(resolve, this.repeatInterval * 1000))
                        }
                        
                        await this.playAudioWithContext(audio)
                    }
                    
                    // 播放完成后，等待间隔时间再播放下一个
                    if (this.audioState.isPlaying) {
                        setTimeout(() => this.nextWord(), this.repeatInterval * 1000)
                    }
                } else {
                    // 其他浏览器使用普通的Audio对象播放
                    audio.onended = async () => {
                        if (!this.audioState.isPlaying) return
                        
                        this.audioState.currentRepeatCount++
                        if (this.audioState.currentRepeatCount < this.repeatCount) {
                            setTimeout(() => {
                                if (this.audioState.isPlaying) {
                                    audio.currentTime = 0
                                    audio.play().catch(error => {
                                        console.error('重复播放失败:', error)
                                        this.showError('播放失败，请点击"重播当前词语"按钮')
                                    })
                                }
                            }, this.repeatInterval * 1000)
                        } else {
                            setTimeout(() => {
                                if (this.audioState.isPlaying) {
                                    this.nextWord()
                                }
                            }, this.repeatInterval * 1000)
                        }
                    }
                    
                    await audio.play()
                }
                
            } catch (error) {
                console.error('播放失败:', error)
                this.showError('播放失败: ' + error.message)
            }
        },
        
        // 使用Web Speech API播放
        playWithWebSpeech() {
            const utterance = new SpeechSynthesisUtterance(this.currentWord)
            utterance.voice = speechSynthesis.getVoices()
                .find(voice => voice.name === this.selectedVoice)
            utterance.rate = this.rate
            
            this.autoPlay.currentRepeatCount = 0
            
            utterance.onend = () => {
                this.autoPlay.currentRepeatCount++
                if (this.autoPlay.currentRepeatCount < this.repeatCount) {
                    // 设置定时器等待指定间隔后重复播放
                    setTimeout(() => speechSynthesis.speak(utterance), 
                        this.repeatInterval * 1000)
                } else {
                    // 重复次数达到后，自动播放下一个词语
                    setTimeout(() => this.nextWord(), this.repeatInterval * 1000)
                }
            }
            
            speechSynthesis.speak(utterance)
        },
        
        // 下一个单词
        nextWord() {
            if (!this.isDictating) return
            
            if (this.currentIndex < this.words.length - 1) {
                this.currentIndex++
                this.playCurrentWord()
            } else {
                alert('听写完成！')
                this.stopDictation()
            }
        },
        
        // 停止听写
        stopDictation() {
            this.isDictating = false
            this.currentWord = ''
            this.currentIndex = 0
            
            // 停止所有音频播放
            this.audioState.isPlaying = false
            
            if (!this.browser.isWechat && this.audioState.currentAudio) {
                this.audioState.currentAudio.pause()
                this.audioState.currentAudio.src = ''
            }
            
            this.audioState.currentAudio = null
            
            // 清理音频队列
            if (!this.browser.isWechat) {
                this.audioState.audioQueue.forEach(audio => {
                    if (audio) {
                        audio.pause()
                        audio.src = ''
                    }
                })
            }
            this.audioState.audioQueue = []
            
            // 重置状态
            this.audioState.currentRepeatCount = 0
            
            // 清除定时器
            if (this.autoPlay.timer) {
                clearTimeout(this.autoPlay.timer)
                this.autoPlay.timer = null
            }
        },
        
        // 轮询系统状态
        startStatusPolling() {
            setInterval(async () => {
                try {
                    const response = await axios.get('/api/status')
                    if (response.data.success) {
                        this.status = response.data.data
                    }
                } catch (error) {
                    console.error('获取状态失败:', error)
                }
            }, 5000) // 每5秒更新一次
        },
        
        // 生成 MP3
        async generateMP3() {
            if (!this.selectedGrade || !this.selectedLesson) {
                this.showError('请先选择年级和课时')
                return
            }
            
            this.isGenerating = true
            this.mp3Url = null
            
            try {
                // 加载单词列表
                const response = await axios.get(
                    `/api/lessons/${encodeURIComponent(this.selectedGrade)}/${encodeURIComponent(this.selectedLesson)}/words`
                )
                
                if (!response.data.success) {
                    throw new Error('加载单词失败: ' + response.data.message)
                }
                
                let words = response.data.data.words
                if (this.playMode === 'random') {
                    // 随机打乱单词顺序
                    words = words
                        .map(value => ({ value, sort: Math.random() }))
                        .sort((a, b) => a.sort - b.sort)
                        .map(({ value }) => value)
                }
                
                // 生成音频文件
                const audioResponse = await axios.post('/api/tts/batch', {
                    words: words,
                    engine: this.ttsEngine,
                    voice: this.selectedVoice,
                    rate: this.rate,
                    repeatCount: this.repeatCount,
                    repeatInterval: this.repeatInterval,
                    grade: this.selectedGrade,  // 添加年级
                    lesson: this.selectedLesson  // 添加课时
                }, {
                    responseType: 'blob'
                })
                
                // 创建下载链接
                const url = URL.createObjectURL(audioResponse.data)
                this.mp3Url = url
                
            } catch (error) {
                this.showError('生成MP3失败: ' + (error.response?.data?.detail || error.message))
            } finally {
                this.isGenerating = false
            }
        },
        
        // 检查缓存
        async checkCache(words) {
            this.cacheStatus.isChecking = true
            this.cacheStatus.progress = 0
            this.cacheStatus.total = words.length
            
            try {
                const response = await fetch('/api/tts/check-cache', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        words: words,
                        engine: this.ttsEngine,
                        voice: this.selectedVoice,
                        rate: this.rate
                    })
                })

                const reader = response.body.getReader()
                const decoder = new TextDecoder()

                while (true) {
                    const { value, done } = await reader.read()
                    if (done) break
                    
                    const lines = decoder.decode(value).trim().split('\n')
                    for (const line of lines) {
                        if (!line.trim()) continue  // 跳过空行
                        
                        try {
                            console.log('收到的数据:', line)  // 添加日志
                            const data = JSON.parse(line)
                            console.log('解析后的数据:', data)  // 添加日志
                            
                            this.cacheStatus.progress = data.progress
                            this.cacheStatus.total = data.total
                            
                            if (data.ready !== undefined) {
                                if (!data.ready) {
                                    throw new Error(`以下单词缓存失败: ${data.failed_words.join(', ')}`)
                                }
                                return true
                            }
                        } catch (e) {
                            console.error('解析进度数据失败:', e, '原始数据:', line)
                        }
                    }
                }
                
                return false  // 如果循环正常结束但没有收到最终结果
            } catch (error) {
                console.error('检查缓存失败:', error)
                this.showError(error.message || '检查缓存失败')
                return false
            } finally {
                this.cacheStatus.isChecking = false
            }
        }
    },
    
    watch: {
        // 监听年级变化
        selectedGrade() {
            this.loadLessons()
        },
        
        // 监听TTS引擎变化
        ttsEngine() {
            this.loadVoices()
        }
    },
    
    // 页面加载完成后初始化
    mounted() {
        this.init()
    }
})

// 挂载应用
app.mount('#app') 