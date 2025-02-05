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
            mp3Url: null
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
            await this.loadGrades()
            await this.loadVoices()
            this.startStatusPolling()
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
                    this.words = response.data.data.words
                    if (this.playMode === 'random') {
                        // 随机打乱单词顺序
                        this.words = this.words
                            .map(value => ({ value, sort: Math.random() }))
                            .sort((a, b) => a.sort - b.sort)
                            .map(({ value }) => value)
                    }
                    
                    this.currentIndex = 0
                    this.isDictating = true
                    this.playCurrentWord()
                } else {
                    this.showError('加载单词失败: ' + response.data.message)
                }
            } catch (error) {
                this.showError('加载单词失败: ' + (error.response?.data?.detail || error.message))
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
            
            // 使用Edge TTS
            try {
                const headers = { 'X-Session-ID': this.sessionId }
                const response = await axios.post('/api/tts', {
                    text: this.currentWord,
                    engine: this.ttsEngine,
                    voice: this.selectedVoice,
                    rate: this.rate
                }, {
                    headers,
                    responseType: 'blob'
                })
                
                const audio = new Audio(URL.createObjectURL(response.data))
                this.autoPlay.currentRepeatCount = 0
                
                audio.onended = () => {
                    this.autoPlay.currentRepeatCount++
                    if (this.autoPlay.currentRepeatCount < this.repeatCount) {
                        // 设置定时器等待指定间隔后重复播放
                        setTimeout(() => audio.play(), this.repeatInterval * 1000)
                    } else {
                        // 重复次数达到后，自动播放下一个词语
                        setTimeout(() => this.nextWord(), this.repeatInterval * 1000)
                    }
                }
                
                audio.play()
            } catch (error) {
                this.showError('播放失败: ' + (error.response?.data?.detail || error.message))
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
            this.autoPlay.currentRepeatCount = 0
            // 清除可能存在的定时器
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
                    repeatInterval: this.repeatInterval
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