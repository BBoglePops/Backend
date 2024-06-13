from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import JSONParser
from .models import InterviewAnalysis, QuestionLists
import os
from django.conf import settings
import logging
import requests



# 이서 import 항목
from google.cloud import speech
from rest_framework.parsers import MultiPartParser, FormParser
from google.cloud.speech import RecognitionConfig, RecognitionAudio
from google.oauth2 import service_account
from django.conf import settings
from pydub import AudioSegment
import nltk
from nltk.tokenize import word_tokenize
import difflib
import parselmouth
import numpy as np
import base64
import io
import re
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import nltk
import matplotlib
matplotlib.use('Agg')  # 백엔드를 Agg로 설정

from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import JSONParser
from .models import InterviewAnalysis, QuestionLists
import os
from django.conf import settings
import logging
import requests
import re

logger = logging.getLogger(__name__)

class ResponseAPIView(APIView):
    parser_classes = [JSONParser]
    permission_classes = [IsAuthenticated]

    REDUNDANT_EXPRESSIONS = [" 어 ", " 음 ", " 음... ", " 그러니까 ", " 이제 ", " 사실은 ", " 그래서 ", " 아니면 ", " 막 ", " 이런 ", " 진짜 ", " 이거 ", " 이렇게 ", " 뭐 ", " 아니 ", " 그냥 "]

    def post(self, request, question_list_id):
        question_list = get_object_or_404(QuestionLists, id=question_list_id)
        interview_response = InterviewAnalysis(question_list=question_list)

        # 로그인한 사용자를 user 필드에 할당
        interview_response.user = request.user

        response_data = []
        all_responses = ""
        for i in range(1, 11):
            script_key = f'script_{i}'
            question_key = f'question_{i}'
            script_text = request.data.get(script_key, "")
            question_text = getattr(question_list, question_key, "")

            # GPT API를 사용하여 표현을 분석
            prompt = f"다음은 면접 응답입니다:\n{script_text}\n\n이 응답에서 면접 시 사용을 지양해야 하는 표현과 그에 대한 수정 사항을 알려주세요. 또한 잉여적인 표현을 검출해 주세요."
            try:
                response = requests.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
                    json={"model": "gpt-3.5-turbo", "messages": [{"role": "user", "content": prompt}]},
                    timeout=10
                )
                response.raise_for_status()
                analysis_result = response.json().get('choices')[0].get('message').get('content')

                # 분석 결과 파싱
                inappropriateness = self.extract_inappropriateness(analysis_result)
                corrections = self.extract_corrections(analysis_result)
                redundancies = self.extract_redundancies(script_text)
                corrected_response = self.apply_corrections(script_text, corrections, redundancies)

                setattr(interview_response, f'response_{i}', script_text)
                setattr(interview_response, f'redundancies_{i}', ', '.join(redundancies))
                setattr(interview_response, f'inappropriateness_{i}', ', '.join(inappropriateness))
                setattr(interview_response, f'corrections_{i}', str(corrections))
                setattr(interview_response, f'corrected_response_{i}', corrected_response)

                response_data.append({
                    'question': question_text,
                    'response': script_text,
                    'redundancies': redundancies,
                    'inappropriateness': inappropriateness,
                    'corrections': corrections,
                })

                if script_text:
                    all_responses += f"{script_text}\n"

            except requests.exceptions.RequestException as e:
                logger.error(f"GPT API request failed: {e}")
                return Response({"error": "GPT API request failed", "details": str(e)}, status=500)

        interview_response.save()

        overall_prompt = f"다음은 사용자의 면접 응답입니다:\n{all_responses}\n\n응답이 직무연관성, 문제해결력, 의사소통능력, 성장가능성, 인성과 관련하여 적절했는지 300자 내외로 총평을 작성해줘."
        try:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
                json={"model": "gpt-3.5-turbo-0125", "messages": [{"role": "user", "content": overall_prompt}]},
                timeout=10
            )
            response.raise_for_status()
            gpt_feedback = response.json().get('choices')[0].get('message').get('content')
            interview_response.overall_feedback = gpt_feedback  # 총평을 overall_feedback 필드에 저장
        except requests.exceptions.RequestException as e:
            logger.error(f"GPT API request failed: {e}")
            gpt_feedback = "총평을 가져오는 데 실패했습니다."
            interview_response.overall_feedback = gpt_feedback  # 실패 메시지를 저장

        interview_response.save()  # 변경 사항 저장

        return Response({
            'interview_id': interview_response.id,
            'responses': response_data,
            'gpt_feedback': gpt_feedback
        }, status=200)

    def extract_inappropriateness(self, analysis_result):
        # 분석 결과에서 부적절한 표현을 추출하는 로직
        match = re.search(r'부적절한 표현:\s*(.*?)\s*수정 사항:', analysis_result, re.DOTALL)
        if match:
            return match.group(1).strip().split(', ')
        return []

    def extract_corrections(self, analysis_result):
        # 분석 결과에서 수정 사항을 추출하는 로직
        match = re.search(r'수정 사항:\s*(.*?)\s*잉여 표현:', analysis_result, re.DOTALL)
        if match:
            corrections_list = match.group(1).strip().split(', ')
            corrections = {}
            for correction in corrections_list:
                term, replacement = correction.split(' -> ')
                corrections[term.strip()] = replacement.strip()
            return corrections
        return {}

    def extract_redundancies(self, script_text):
        # 잉여 표현을 추출하는 로직
        redundancies = []
        for expr in self.REDUNDANT_EXPRESSIONS:
            if f" {expr} " in f" {script_text} ":
                redundancies.append(expr.strip())
        return redundancies

    def apply_corrections(self, script_text, corrections, redundancies):
        # 원본 텍스트에 수정 사항을 적용하는 로직
        for term, replacement in corrections.items():
            script_text = script_text.replace(term, replacement)
        for expr in redundancies:
            script_text = script_text.replace(f" {expr} ", " ")
        return script_text

# logger = logging.getLogger(__name__)


# # 답변 스크립트 분석
# class ResponseAPIView(APIView):
#     parser_classes = [JSONParser]
#     permission_classes = [IsAuthenticated]

#     def post(self, request, question_list_id):
#         question_list = get_object_or_404(QuestionLists, id=question_list_id)
#         interview_response = InterviewAnalysis(question_list=question_list)

#         # 로그인한 사용자를 user 필드에 할당
#         interview_response.user = request.user

#         base_dir = settings.BASE_DIR
#         redundant_expressions_path = os.path.join(base_dir, 'InterviewAnalyze', 'redundant_expressions.txt')
#         inappropriate_terms_path = os.path.join(base_dir, 'InterviewAnalyze', 'inappropriate_terms.txt')

#         try:
#             with open(redundant_expressions_path, 'r') as file:
#                 redundant_expressions = file.read().splitlines()
#             with open(inappropriate_terms_path, 'r') as file:
#                 inappropriate_terms = dict(line.strip().split(':') for line in file if ':' in line)
#         except FileNotFoundError as e:
#             logger.error(f"File not found: {e}")
#             return Response({"error": "Required file not found"}, status=500)

#         response_data = []
#         all_responses = ""
#         for i in range(1, 11):
#             script_key = f'script_{i}'
#             response_key = f'response_{i}'
#             question_key = f'question_{i}'
#             script_text = request.data.get(script_key, "")
#             question_text = getattr(question_list, question_key, "")

#             # 잉여 표현과 부적절한 표현을 분석
#             found_redundant = [expr for expr in redundant_expressions if expr in script_text]
#             corrections = {}
#             corrected_text = script_text
#             for term, replacement in inappropriate_terms.items():
#                 if term in script_text:
#                     corrections[term] = replacement
#                     corrected_text = corrected_text.replace(term, replacement)

#             setattr(interview_response, f'response_{i}', script_text)
#             setattr(interview_response, f'redundancies_{i}', ', '.join(found_redundant))
#             setattr(interview_response, f'inappropriateness_{i}', ', '.join(corrections.keys()))
#             setattr(interview_response, f'corrections_{i}', str(corrections))
#             setattr(interview_response, f'corrected_response_{i}', corrected_text)

#             response_data.append({
#                 'question': question_text,
#                 'response': script_text,
#                 'redundancies': found_redundant,
#                 'inappropriateness': list(corrections.keys()),
#                 'corrections': corrections,
#                 'corrected_response': corrected_text,
#             })

#             if script_text:
#                 all_responses += f"{script_text}\n"

#         interview_response.save()

#         prompt = f"다음은 사용자의 면접 응답입니다:\n{all_responses}\n\n응답이 직무연관성, 문제해결력, 의사소통능력, 성장가능성, 인성과 관련하여 적절했는지 300자 내외로 총평을 작성해줘."
#         try:
#             response = requests.post(
#                 "https://api.openai.com/v1/chat/completions",
#                 headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
#                 json={"model": "gpt-3.5-turbo-0125", "messages": [{"role": "user", "content": prompt}]},
#                 timeout=10
#             )
#             response.raise_for_status()
#             gpt_feedback = response.json().get('choices')[0].get('message').get('content')
#             interview_response.overall_feedback = gpt_feedback  # 총평을 overall_feedback 필드에 저장
#         except requests.exceptions.RequestException as e:
#             logger.error(f"GPT API request failed: {e}")
#             gpt_feedback = "총평을 가져오는 데 실패했습니다."
#             interview_response.overall_feedback = gpt_feedback  # 실패 메시지를 저장

#         interview_response.save()  # 변경 사항 저장

#         return Response({
#             'interview_id': interview_response.id,
#             'responses': response_data,
#             'gpt_feedback': gpt_feedback
#         }, status=200)


# 여기서부터 이서코드
nltk.download('punkt') # 1회만 다운로드 하면댐

def set_korean_font():
    font_path = os.path.join(settings.BASE_DIR, 'fonts', 'NanumGothic.ttf')
    if not os.path.isfile(font_path):
        raise RuntimeError(f"Font file not found: {font_path}")
    font_prop = fm.FontProperties(fname=font_path)
    plt.rc('font', family=font_prop.get_name())

credentials = service_account.Credentials.from_service_account_file(
    os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
) 

class VoiceAPIView(APIView):
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # 현재 로그인한 사용자의 인터뷰 분석 결과를 조회
        interview_responses = InterviewAnalysis.objects.filter(user=request.user).order_by('-created_at')
        data = []
        for interview in interview_responses:
            data.append({
                'interview_id': interview.id,
                'pronunciation_similarity': interview.pronunciation_similarity,
                'pitch_analysis': interview.pitch_analysis,
                'intensity_analysis': interview.intensity_analysis,
                'pronunciation_message': interview.pronunciation_message,
                'pitch_message': interview.pitch_message,
                'intensity_message': interview.intensity_message,
                'response_1': interview.response_1,
                'response_2': interview.response_2,
                'response_3': interview.response_3,
                'response_4': interview.response_4,
                'response_5': interview.response_5,
                'response_6': interview.response_6,
                'response_7': interview.response_7,
                'response_8': interview.response_8,
                'response_9': interview.response_9,
                'response_10': interview.response_10,
            })
        return Response(data, status=200)

    def post(self, request, question_list_id=None):
        question_id = request.data.get('question_id')
        if question_list_id:
            return self.handle_response_analysis(request, question_list_id, question_id)
        else:
            return self.handle_audio_analysis(request)

    def handle_response_analysis(self, request, question_list_id, question_id):
        question_list = get_object_or_404(QuestionLists, id=question_list_id)
        interview_response = InterviewAnalysis(question_list=question_list, user=request.user)

        client = speech.SpeechClient(credentials=credentials)
        audio_file_path = None

        file_key = f'audio_{question_id}'  # question_id를 사용하여 파일 키 생성
        if file_key in request.FILES:
            audio_file = request.FILES[file_key]
            audio_file_path = os.path.join(settings.MEDIA_ROOT, audio_file.name)
            with open(audio_file_path, 'wb') as f:
                f.write(audio_file.read())
                
            logger.debug(f"Audio file saved at: {audio_file_path}")

            # mp3 파일을 wav 파일로 변환
            try:
                audio_segment = AudioSegment.from_file(audio_file_path, format="mp3")
                wav_audio_path = audio_file_path.replace(".mp3", ".wav")
                audio_segment.export(wav_audio_path, format="wav")
                logger.debug(f"Converted wav audio saved at: {wav_audio_path}")
            except Exception as e:
                logger.error(f"Error converting audio file: {str(e)}")
                return Response({"error": "Error converting audio file", "details": str(e)}, status=500)

            sample_rate = audio_segment.frame_rate

            config = RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=sample_rate,  # 동적으로 샘플링 속도 설정
                language_code="ko-KR",
                max_alternatives=2
            )

            try:
                with open(wav_audio_path, 'rb') as wav_file:
                    audio_content = wav_file.read()

                audio = RecognitionAudio(content=audio_content)
                response = client.recognize(config=config, audio=audio)
                
                logger.debug(f"Response results: {response.results}")
            except Exception as e:
                logger.error(f"Error in speech recognition: {str(e)}")
                return Response({"error": "Error in speech recognition", "details": str(e)}, status=500)

            try:
                highest_confidence_text = ' '.join([result.alternatives[0].transcript for result in response.results if result.alternatives])
                most_raw_text = ' '.join([result.alternatives[1].transcript for result in response.results if len(result.alternatives) > 1])
            except IndexError as e:
                logger.error(f"IndexError in response analysis: {str(e)}")
                logger.error(f"Response content: {response}")
                highest_confidence_text = ""
                most_raw_text = ""
        else:
            highest_confidence_text = ""
            most_raw_text = ""

        highlighted_response = self.highlight_differences(most_raw_text, highest_confidence_text, question_id)  # 하이라이팅된 응답 생성
        setattr(interview_response, f'response_{question_id}', highlighted_response)  # 하이라이팅된 응답 저장

        question_key = f'question_{question_id}'
        question_text = getattr(question_list, question_key, None)
        response_text = getattr(interview_response, f'response_{question_id}', None)

        response_data = {
            'question': question_text,
            'response': response_text,
        }

        # 발음 분석 및 피치 분석 수행
        pronunciation_result = None
        pitch_result = None
        intensity_result = None

        if audio_file_path:
            pronunciation_result, pronunciation_message = self.analyze_pronunciation(audio_file_path, most_raw_text, highest_confidence_text, question_id)  # question_id 전달
            pitch_result, intensity_result, pitch_graph_base64, intensity_graph_base64, intensity_message, pitch_message = self.analyze_pitch(audio_file_path)

            # 분석 결과를 인터뷰 응답 객체에 저장
            interview_response.pronunciation_similarity = str(pronunciation_result)
            interview_response.pitch_analysis = str(pitch_result)
            interview_response.intensity_analysis = str(intensity_result)
            interview_response.pronunciation_message = pronunciation_message
            interview_response.pitch_message = pitch_message
            interview_response.intensity_message = intensity_message

        interview_response.save()

        return Response({
            'interview_id': interview_response.id,
            'response': response_data,
            'pronunciation_similarity': pronunciation_result,
            'pitch_analysis': pitch_result,
            'intensity_analysis': intensity_result,
            'intensity_message': intensity_message,
            'pitch_message': pitch_message,
            'pronunciation_message': pronunciation_message
        }, status=200)

    def handle_audio_analysis(self, request):
        question_list_id = request.data.get('question_list_id')
        if not question_list_id:
            return Response({"error": "question_list_id is required"}, status=400)

        question_list = get_object_or_404(QuestionLists, id=question_list_id)
        
        try:
            # 오디오 파일 확인
            audio_files = [request.FILES.get(f'audio_{i}') for i in range(1, 11) if request.FILES.get(f'audio_{i}')]

            if not audio_files:
                return Response({"error": "Audio files not provided"}, status=400)
            
            # 오디오 파일들을 하나로 병합 및 모노로 변환
            combined_audio_segments = []
            for audio_file in audio_files:
                audio_temp_path = os.path.join(settings.MEDIA_ROOT, audio_file.name)
                with open(audio_temp_path, 'wb') as f:
                    f.write(audio_file.read())

                # mp3 파일을 wav 파일로 변환
                audio_segment = AudioSegment.from_file(audio_temp_path, format="mp3")
                combined_audio_segments.append(audio_segment.set_channels(1))  # 모노로 변환

            combined_audio = sum(combined_audio_segments)
            sample_rate = combined_audio.frame_rate

            combined_audio_path = os.path.join(settings.MEDIA_ROOT, 'combined_audio.wav')
            combined_audio.export(combined_audio_path, format='wav')

            logger.debug(f"Combined audio path: {combined_audio_path}")

            # 발음 분석 결과 가져오기
            pronunciation_result, highest_confidence_text, average_similarity, pronunciation_message = self.analyze_pronunciation(combined_audio_path, sample_rate=sample_rate)

            logger.debug(f"Pronunciation result: {pronunciation_result}")
            logger.debug(f"Highest confidence text: {highest_confidence_text}")

            # 피치 분석 결과 가져오기
            pitch_result, intensity_result, pitch_graph_base64, intensity_graph_base64, intensity_message, pitch_message = self.analyze_pitch(combined_audio_path)

            logger.debug(f"Pitch result: {pitch_result}")
            logger.debug(f"Intensity result: {intensity_result}")

            # 인터뷰 응답 객체 생성 및 저장
            interview_response = InterviewAnalysis(
                user=request.user,
                question_list=question_list,
                pronunciation_similarity=str(pronunciation_result),
                pitch_analysis=str(pitch_result),
                intensity_analysis=str(intensity_result),
                pronunciation_message=pronunciation_message,
                pitch_message=pitch_message,
                intensity_message=intensity_message
            )
            interview_response.save()

            # JSON 형식의 결과 반환
            return Response({
                "interview_id": interview_response.id,
                "pronunciation_similarity": pronunciation_result,
                "highest_confidence_text": highest_confidence_text,
                "average_similarity": average_similarity,
                "pitch_analysis": pitch_result,
                "intensity_analysis": intensity_result,
                "pitch_graph": pitch_graph_base64,
                "intensity_graph": intensity_graph_base64,
                "intensity_message": intensity_message,
                "pitch_message": pitch_message,
                "pronunciation_message": pronunciation_message
            }, status=200)

        except FileNotFoundError as e:
            logger.error(f"File not found: {str(e)}")
            return Response({"error": "File not found", "details": str(e)}, status=500)
        except PermissionError as e:
            logger.error(f"Permission denied: {str(e)}")
            return Response({"error": "Permission denied", "details": str(e)}, status=500)
        except Exception as e:
            logger.error(f"Unexpected error in VoiceAPIView: {str(e)}")
            return Response({"error": "Internal Server Error", "details": str(e)}, status=500)

    def combine_audio_files(self, audio_files):
        """여러 개의 오디오 파일을 하나로 병합하고 모노로 변환"""
        combined = AudioSegment.empty()
        sample_rate = None

        for audio_file in audio_files:
            audio_segment = AudioSegment.from_file(audio_file)
            audio_segment = audio_segment.set_channels(1)  # 모노로 변환

            if sample_rate is None:
                sample_rate = audio_segment.frame_rate
            elif sample_rate != audio_segment.frame_rate:
                audio_segment = audio_segment.set_frame_rate(sample_rate)  # 프레임 레이트를 통일

            combined += audio_segment
        return combined, sample_rate

    def analyze_pronunciation(self, audio_file_path, most_raw_text=None, highest_confidence_text=None, question_id=None, sample_rate=None):  
        """음성 파일의 발음 분석을 수행합니다."""
        with open(audio_file_path, 'rb') as audio_file:
            audio_content = audio_file.read()
        logger.debug(f"Audio content length: {len(audio_content)}")

        audio = RecognitionAudio(content=audio_content)
        config = RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=sample_rate,  
            language_code='ko-KR',
            enable_automatic_punctuation=True,
            max_alternatives=2  # 2개의 대안을 요청
        )

        client = speech.SpeechClient(credentials=credentials)
        try:
            operation = client.long_running_recognize(config=config, audio=audio)
            response = operation.result(timeout=90)
        except Exception as e:
            logger.error(f"Error in long_running_recognize: {str(e)}")
            raise e

        logger.debug(f"Pronunciation response results: {response.results}")
        if response.results:
            try:
                highest_confidence_text = response.results[0].alternatives[0].transcript if len(response.results[0].alternatives) > 0 else ""
                most_raw_text = response.results[0].alternatives[1].transcript if len(response.results[0].alternatives) > 1 else highest_confidence_text
            except IndexError as e:
                logger.error(f"IndexError in pronunciation analysis: {str(e)}")
                logger.error(f"Response content: {response}")
                highest_confidence_text = ""
                most_raw_text = ""
        else:
            highest_confidence_text = ""
            most_raw_text = ""

        expected_sentences = re.split(r'[.!?]', most_raw_text)
        received_sentences = re.split(r'[.!?]', highest_confidence_text)

        pronunciation_result = []
        total_similarity = 0
        num_sentences = 0

        for expected_sentence, received_sentence in zip(expected_sentences, received_sentences):
            similarity = difflib.SequenceMatcher(None, expected_sentence.strip(), received_sentence.strip()).ratio()
            total_similarity += similarity
            num_sentences += 1
            highlighted_received_sentence = self.highlight_differences(expected_sentence.strip(), received_sentence.strip(), similarity)
            pronunciation_result.append({
                'question_id': question_id,  # question_id 추가
                '실제 발음': expected_sentence.strip(),
                '기대 발음': highlighted_received_sentence,
                '유사도': similarity
            })

        average_similarity = total_similarity / num_sentences if num_sentences > 0 else 0

        # 발음 유사도에 따른 메시지
        if average_similarity >= 0.91:
            pronunciation_message = "훌륭한 발음을 보여주셨습니다. 면접관들에게 전달하고자 하는 메시지를 명확하게 전달할 수 있는 발음입니다. 이대로 계속 연습하면 좋은 결과가 있을 것입니다."
        elif 0.81 <= average_similarity < 0.91:
            pronunciation_message = "발음이 전반적으로 괜찮습니다만, 일부 단어에서 조금 더 명확하게 발음하려는 노력이 필요할 것 같습니다. 특히 긴장하거나 빠르게 말할 때 발음이 흐려질 수 있으니, 천천히 말하며 연습해 보세요."
        else:
            pronunciation_message = "발음 연습이 조금 더 필요해 보입니다. 면접관에게 전달하고자 하는 메시지를 명확하게 전달하기 위해 중요한 단어들을 뚜렷하게 발음하는 연습을 추천드립니다. 꾸준한 연습을 통해 발음을 개선해 나가면 좋겠습니다."

        return pronunciation_result, highest_confidence_text, average_similarity, pronunciation_message

    def highlight_differences(self, expected_sentence, received_sentence, similarity):
        """예상 문장과 받은 문장의 차이점을 강조합니다."""
        if similarity > 0.9:
            return received_sentence  # similarity가 0.9 이상이면 강조하지 않음

        sequence_matcher = difflib.SequenceMatcher(None, expected_sentence, received_sentence)
        highlighted_received_sentence = ""
        for opcode, a0, a1, b0, b1 in sequence_matcher.get_opcodes():
            if opcode == 'equal':
                highlighted_received_sentence += received_sentence[b0:b1]
            elif opcode == 'replace' or opcode == 'insert':
                highlighted_received_sentence += f"<span style='color:blue;'>{received_sentence[b0:b1]}</span>"
            elif opcode == 'delete':
                highlighted_received_sentence += f"<span style='color:blue;'></span>"
        return highlighted_received_sentence

    def analyze_pitch(self, audio_file_path):
        """음성 파일의 피치 분석을 수행하고 그래프를 생성합니다."""
        set_korean_font()  # 한글 폰트 설정

        sound = parselmouth.Sound(audio_file_path)

        pitch = sound.to_pitch()
        pitch_values = pitch.selected_array['frequency']
        pitch_times = pitch.xs()

        intensity = sound.to_intensity()
        intensity_values = intensity.values.T
        intensity_times = intensity.xs()

        # 0이 아닌 피치 값과 강도 값 필터링
        non_zero_pitch_values = pitch_values[pitch_values > 0]
        non_zero_intensity_values = intensity_values[intensity_values > 0]

        # 피치 그래프 생성
        fig, ax1 = plt.subplots(figsize=(12, 4))
        ax1.plot(pitch_times / 60, pitch_values, 'o', markersize=2, label='강도')
        ax1.plot(pitch_times / 60, np.where((pitch_values >= 150) & (pitch_values <= 500), pitch_values, np.nan), 'o', markersize=2, color='blue', label='일반적(150-500Hz)')
        ax1.plot(pitch_times / 60, np.where((pitch_values < 150) | (pitch_values > 500), pitch_values, np.nan), 'o', markersize=2, color='red', label='범위 밖')
        ax1.set_xlabel('시간(분)')
        ax1.set_ylabel('피치(Hz)')
        ax1.set_title('피치')
        ax1.set_xlim([0, max(pitch_times / 60)])
        ax1.set_ylim([0, 500])
        ax1.grid(True)
        ax1.legend()
        ax1.set_xticks(np.arange(0, max(pitch_times / 60), 1))

        buf = io.BytesIO()
        plt.tight_layout()
        plt.savefig(buf, format='png')
        buf.seek(0)
        pitch_graph_base64 = base64.b64encode(buf.read()).decode('utf-8')
        buf.close()
        plt.close(fig)

        # 강도 그래프 생성
        fig, ax2 = plt.subplots(figsize=(12, 4))
        ax2.plot(intensity_times / 60, intensity_values, linewidth=1, label='강도')
        ax2.plot(intensity_times / 60, np.where((intensity_values >= 35) & (intensity_values <= 65), intensity_values, np.nan), linewidth=1, color='blue', label='일반적(35-65db)')
        ax2.plot(intensity_times / 60, np.where((intensity_values < 35) | (intensity_values > 65), intensity_values, np.nan), linewidth=1, color='red', label='범위 밖')
        ax2.set_xlabel('시간(분)')
        ax2.set_ylabel('강도(dB)')
        ax2.set_title('강도')
        ax2.set_xlim([0, max(intensity_times / 60)])
        ax2.set_ylim([0, max(intensity_values)])
        ax2.grid(True)
        ax2.legend()
        ax2.set_xticks(np.arange(0, max(intensity_times / 60), 1))

        buf = io.BytesIO()
        plt.tight_layout()
        plt.savefig(buf, format='png')
        buf.seek(0)
        intensity_graph_base64 = base64.b64encode(buf.read()).decode('utf-8')
        buf.close()
        plt.close(fig)

        pitch_result = {
            'times': (pitch_times / 60).tolist(),  # 분 단위로 변환
            'values': pitch_values.tolist(),
            'min_value': float(np.min(non_zero_pitch_values)),
            'max_value': float(np.max(non_zero_pitch_values)),
            'average_value': float(np.mean(non_zero_pitch_values))
        }

        intensity_result = {
            'times': (intensity_times / 60).tolist(),  # 분 단위로 변환
            'values': intensity_values.tolist(),
            'min_value': float(np.min(non_zero_intensity_values)),
            'max_value': float(np.max(non_zero_intensity_values)),
            'average_value': float(np.mean(non_zero_intensity_values))
        }

        # 강도 평균값 평가
        intensity_avg = intensity_result['average_value']
        if intensity_avg >= 35 and intensity_avg <= 65:
            intensity_message = "목소리 크기가 적당합니다. 면접관이 듣기 좋은 수준의 목소리를 가지고 계십니다. 이 크기로 계속 연습하시면 좋을 것입니다."
        elif intensity_avg < 35:
            intensity_message = "목소리가 다소 작은 편입니다. 면접관에게 자신감 있는 모습을 보여주기 위해 조금 더 크게 말해 보세요. 목소리 크기를 키우는 연습을 통해 더욱 당당한 인상을 줄 수 있습니다."
        else:
            intensity_message = "목소리가 다소 큰 편입니다. 조금만 더 부드럽고 차분하게 말하면 좋을 것 같습니다. 면접관에게 강한 인상을 주는 것도 좋지만, 너무 큰 목소리는 오히려 부담을 줄 수 있습니다."

        # 피치 평균값 평가
        pitch_avg = pitch_result['average_value']
        if pitch_avg >= 150 and pitch_avg <= 450:
            pitch_message = "말씀하시는 속도가 적당합니다. 면접관이 이해하기 쉬운 속도로 말하고 계십니다. 이 속도로 계속 연습하시면 좋을 결과가 있을 것입니다."
        elif pitch_avg < 150:
            pitch_message = "말씀하시는 속도가 다소 느린 편입니다. 조금 더 빠르게 말하면 면접관의 집중력을 유지하는 데 도움이 될 것입니다. 적당한 속도를 유지하며 자연스럽게 말하는 연습을 추천드립니다."
        else:
            pitch_message = "말씀하시는 속도가 조금 빠른 편입니다. 천천히 말하면 면접관이 더 잘 이해할 수 있고, 자신감 있는 모습을 보일 수 있습니다. 천천히 말하는 연습을 통해 전달력을 높여 보세요."

        return pitch_result, intensity_result, pitch_graph_base64, intensity_graph_base64, intensity_message, pitch_message