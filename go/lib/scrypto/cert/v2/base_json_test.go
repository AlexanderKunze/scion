// Copyright 2019 Anapaya Systems
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//   http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package cert_test

import (
	"encoding/json"
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/scionproto/scion/go/lib/scrypto/cert/v2"
)

func TestKeyTypeUnmarshalJSON(t *testing.T) {
	tests := map[string]struct {
		Input     string
		Assertion assert.ErrorAssertionFunc
		Expected  cert.KeyType
	}{
		"Garbage": {
			Input:     `"test"`,
			Assertion: assert.Error,
		},
		"Integer": {
			Input:     `42`,
			Assertion: assert.Error,
		},
		"Wrong case": {
			Input:     `"signing"`,
			Assertion: assert.Error,
		},
		"SigningKey": {
			Input:     `"Signing"`,
			Assertion: assert.NoError,
			Expected:  cert.SigningKey,
		},
		"EncryptionKey": {
			Input:     `"Encryption"`,
			Assertion: assert.NoError,
			Expected:  cert.EncryptionKey,
		},
		"IssuingKey": {
			Input:     `"Issuing"`,
			Assertion: assert.NoError,
			Expected:  cert.IssuingKey,
		},
		"RevocationKey": {
			Input:     `"Revocation"`,
			Assertion: assert.NoError,
			Expected:  cert.RevocationKey,
		},
	}
	for name, test := range tests {
		t.Run(name, func(t *testing.T) {
			var keyType cert.KeyType
			test.Assertion(t, json.Unmarshal([]byte(test.Input), &keyType))
			assert.Equal(t, test.Expected, keyType)
		})
	}
}

func TestKeyTypeUnmarshalJSONMapKey(t *testing.T) {
	tests := map[string]struct {
		Input     string
		Assertion assert.ErrorAssertionFunc
	}{
		"Invalid KeyType": {
			Input: `
			{
				"unknown": "key"
			}`,
			Assertion: assert.Error,
		},
		"Valid": {
			Input: `
			{
				"Issuing": "key"
			}`,
			Assertion: assert.NoError,
		},
	}
	for name, test := range tests {
		t.Run(name, func(t *testing.T) {
			var m map[cert.KeyType]string
			test.Assertion(t, json.Unmarshal([]byte(test.Input), &m))
		})
	}
}

func TestKeyTypeMarshal(t *testing.T) {
	tests := map[string]struct {
		KeyType  cert.KeyType
		Expected string
	}{
		"IssuingKey": {
			KeyType:  cert.IssuingKey,
			Expected: cert.IssuingKeyJSON,
		},
		"SigningKey": {
			KeyType:  cert.SigningKey,
			Expected: cert.SigningKeyJSON,
		},
		"EncryptionKey": {
			KeyType:  cert.EncryptionKey,
			Expected: cert.EncryptionKeyJSON,
		},
		"RevocationKey": {
			KeyType:  cert.RevocationKey,
			Expected: cert.RevocationKeyJSON,
		},
	}
	for name, test := range tests {
		t.Run(name, func(t *testing.T) {
			b, err := json.Marshal(test.KeyType)
			require.NoError(t, err)
			assert.Equal(t, test.Expected, strings.Trim(string(b), `"`))
		})
	}
	t.Run("Invalid value", func(t *testing.T) {
		_, err := json.Marshal(cert.KeyType(100))
		assert.Error(t, err)
	})
}

func TestFormatVersionUnmarshalJSON(t *testing.T) {
	tests := map[string]struct {
		Input     []byte
		Expected  cert.FormatVersion
		Assertion assert.ErrorAssertionFunc
	}{
		"Valid": {
			Input:     []byte("1"),
			Expected:  1,
			Assertion: assert.NoError,
		},
		"Unsupported": {
			Input:     []byte("0"),
			Assertion: assert.Error,
		},
		"String": {
			Input:     []byte(`"0"`),
			Assertion: assert.Error,
		},
		"Garbage": {
			Input:     []byte(`"Garbage"`),
			Assertion: assert.Error,
		},
	}
	for name, test := range tests {
		t.Run(name, func(t *testing.T) {
			var v cert.FormatVersion
			test.Assertion(t, json.Unmarshal(test.Input, &v))
			assert.Equal(t, test.Expected, v)

		})
	}
}