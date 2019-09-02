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

package trc

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"os"

	"github.com/scionproto/scion/go/lib/common"
	"github.com/scionproto/scion/go/lib/scrypto/trc/v2"
	"github.com/scionproto/scion/go/tools/scion-pki/internal/pkicmn"
)

func runHuman(args []string) {
	for _, file := range args {
		if err := genHuman(file); err != nil {
			pkicmn.ErrorAndExit("Error: %s\n", err)
		}
	}
	os.Exit(0)
}

func genHuman(file string) error {
	raw, err := ioutil.ReadFile(file)
	if err != nil {
		return err
	}
	var signed trc.Signed
	if err := json.Unmarshal(raw, &signed); err != nil {
		return common.NewBasicError("unable to parse signed TRC", err, "file", file)
	}
	t, err := signed.EncodedTRC.Decode()
	if err != nil {
		return common.NewBasicError("unable to parse TRC payload", err, "file", file)
	}
	signatures, err := parseSignatures(signed.Signatures)
	if err != nil {
		return common.NewBasicError("unable to parse signatures", err, "file", file)
	}
	humanReadable := struct {
		Payload    *trc.TRC    `json:"payload"`
		Signatures []signature `json:"signatures"`
	}{
		Payload:    t,
		Signatures: signatures,
	}
	if raw, err = json.MarshalIndent(humanReadable, "", "  "); err != nil {
		return common.NewBasicError("unable to write human readable trc", err, "file", file)
	}
	_, err = fmt.Fprintln(os.Stdout, string(raw))
	return err
}

func parseSignatures(packed []trc.Signature) ([]signature, error) {
	var signatures []signature
	for i, s := range packed {
		p, err := s.EncodedProtected.Decode()
		if err != nil {
			return nil, common.NewBasicError("unable to parse protected meta", err, "idx", i)
		}
		signatures = append(signatures, signature{Protected: p, Signature: s.Signature})
	}
	return signatures, nil
}

type signature struct {
	Protected trc.Protected `json:"protected"`
	Signature []byte        `json:"signature"`
}
